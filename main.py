#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import subprocess
import time
import math
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QLabel, 
    QComboBox, QPushButton, QLineEdit, QFileDialog, QMessageBox, QTextEdit,
    QAction, QMenu, QMenuBar, QFrame, QCheckBox, QGroupBox, QGridLayout, QDialog,
    QListWidget, QDialogButtonBox, QListWidgetItem
)
from PyQt5.QtCore import Qt, QProcess, QTimer, QEvent, QObject
from PyQt5.QtGui import QIcon, QFont, QPalette, QColor, QPixmap

from scrcpy_controller import ScrcpyController
from app_manager import AppManagerDialog

# 添加ScrcpyEventMonitor类用于监控设备事件
class ScrcpyEventMonitor(QObject):
    def __init__(self, parent, controller, main_device_id, slave_device_ids):
        super().__init__(parent)
        self.controller = controller
        self.main_device_id = main_device_id
        self.slave_device_ids = slave_device_ids
        self.parent = parent
        self.last_event_time = time.time()
        self.min_event_interval = 0.3  # 降低到300ms，提高响应性
        self.is_monitoring = False  # 添加标志跟踪是否在监控
        
        # 记录最后一次坐标用于计算滑动
        self.last_touch_pos = None
        self.touch_start_time = None
        
        # 监控窗口集合
        self.monitored_windows = []
        self.window_titles = []  # 保存已找到的窗口标题
        
        # 添加操作队列，用于记录最近的操作
        self.action_queue = []
        self.max_queue_size = 10
        
        # 添加操作模式检测
        self.is_continuous_operation = False
        self.consecutive_op_count = 0
        self.last_op_type = None
        
        # 添加同步状态跟踪
        self.sync_in_progress = False  # 是否正在进行同步
        self.last_sync_time = 0  # 上次同步完成时间
        self.sync_success = False
        self.sync_statistics = {
            "total": 0,
            "success": 0,
            "failure": 0
        }
        
        # 更强的日志直接输出控制
        self.immediate_log_update = True
        
        # 增加事件类型计数器
        self.event_counts = {
            "press": 0,
            "release": 0,
            "move": 0,
            "key": 0
        }
        
        print(f"开始监控设备 {main_device_id} 的事件，从设备列表: {slave_device_ids}")
        self.parent.log(f"✅ 开始监控主控设备: {main_device_id}")
        if slave_device_ids:
            self.parent.log(f"✅ 从设备列表: {', '.join(slave_device_ids)}")
        self.parent._force_update_log()
        
        # 找到相关设备窗口并安装事件过滤器
        self.find_and_monitor_windows()
        
        # 启动定时器，定期查找窗口 - 缩短间隔提高响应性
        self.find_timer = QTimer(self)
        self.find_timer.timeout.connect(self.find_and_monitor_windows)
        self.find_timer.start(1000)  # 每1秒查找一次窗口，提高响应性
        
        # 添加定时器检查同步状态
        self.sync_timer = QTimer(self)
        self.sync_timer.timeout.connect(self.update_sync_status)
        self.sync_timer.start(1000)  # 每秒检查一次同步状态
        
        # 添加定时器检查操作模式
        self.mode_check_timer = QTimer(self)
        self.mode_check_timer.timeout.connect(self.check_operation_mode)
        self.mode_check_timer.start(5000)  # 每5秒检查一次操作模式
        
        # 安装全局事件过滤器
        QApplication.instance().installEventFilter(self)
        
        # 输出提示信息
        self.parent.log("⚡ 群控事件监控已启动")
        self.parent.log("💡 提示: 请在主控设备上操作，系统将自动同步到从设备")
        self.parent._force_update_log()
        
        # 立即开始查找窗口
        self.find_device_windows()
    
    def check_operation_mode(self):
        """检查当前操作模式，如果检测到连续操作则调整事件间隔"""
        if not self.is_monitoring:
            return
            
        now = time.time()
        # 清理超过10秒的旧操作
        self.action_queue = [action for action in self.action_queue if now - action["time"] <= 10]
        
        # 如果5秒内有超过3次操作，认为是连续操作模式
        recent_actions = [action for action in self.action_queue if now - action["time"] <= 5]
        
        if len(recent_actions) >= 3:
            if not self.is_continuous_operation:
                self.is_continuous_operation = True
                self.min_event_interval = 0.5  # 连续操作模式下增加事件间隔
                self.parent.log("🔄 检测到连续操作模式，已增加同步延迟")
                self.parent._force_update_log()
        else:
            if self.is_continuous_operation:
                self.is_continuous_operation = False
                self.min_event_interval = 0.3  # 恢复正常间隔
                self.parent.log("🔄 恢复正常操作模式")
                self.parent._force_update_log()
    
    def record_action(self, action_type, coords=None):
        """记录一个操作到队列"""
        self.action_queue.append({
            "type": action_type,
            "coords": coords,
            "time": time.time()
        })
        
        # 限制队列大小
        if len(self.action_queue) > self.max_queue_size:
            self.action_queue.pop(0)
            
        # 检测连续相同操作
        if self.last_op_type == action_type:
            self.consecutive_op_count += 1
            if self.consecutive_op_count >= 3:
                # 连续3次相同操作，增加事件间隔
                self.min_event_interval = min(0.8, self.min_event_interval + 0.1)
                self.parent.log(f"⚠️ 检测到连续{action_type}操作，已增加操作间隔")
                self.parent._force_update_log()
        else:
            self.consecutive_op_count = 0
            self.last_op_type = action_type
            
    def find_and_monitor_windows(self):
        """查找设备窗口并监视它们"""
        print("[调试] 执行 find_and_monitor_windows")
        self.parent.log("[调试] 执行 find_and_monitor_windows")
        if not self.is_monitoring:
            self.is_monitoring = True
            self.parent.log("🔍 开始查找设备窗口...")
            self.parent._force_update_log()
        
        # 使用设备窗口识别方法
        self.find_device_windows()
        
        # 如果找不到任何窗口，更新扫描计数
        if not self.monitored_windows:
            scan_count = getattr(self, '_scan_count', 0) + 1
            self._scan_count = scan_count
            
            # 每4次扫描才显示一次未找到窗口的消息，避免过多日志
            if scan_count % 4 == 0:
                self.parent.log("⚠️ 提示: 点击设备窗口,帮助识别监控目标")
                self.parent._force_update_log()
        
        # 输出监控状态
        if self.monitored_windows:
            window_count = len(self.monitored_windows)
            if getattr(self, '_last_window_count', 0) != window_count:
                self.parent.log(f"📊 当前监控 {window_count} 个窗口")
                self.parent._force_update_log()
                self._last_window_count = window_count
        print(f"[调试] 当前已监控窗口: {[w.windowTitle() for w in self.monitored_windows if hasattr(w, 'windowTitle')]}")
        self.parent.log(f"[调试] 当前已监控窗口: {[w.windowTitle() for w in self.monitored_windows if hasattr(w, 'windowTitle')]}")
    
    def update_sync_status(self):
        """更新同步状态指示"""
        # 如果正在同步并且超过8秒，认为同步已超时
        if self.sync_in_progress and time.time() - self.last_event_time > 8.0:
            self.sync_in_progress = False
            self.sync_statistics["failure"] += 1
            self.sync_statistics["total"] += 1
            self.parent.log("⚠️ 同步操作超时，可能未成功")
    
    def show_sync_feedback(self, success=True, message=""):
        """显示同步反馈信息"""
        self.sync_in_progress = False
        self.last_sync_time = time.time()
        self.sync_success = success
        
        # 更新统计信息
        if not hasattr(self, "_last_update") or time.time() - self._last_update > 1.0:
            self._last_update = time.time()
            
            # 显示详细日志
            if message:
                if success:
                    self.parent.log(f"✅ 同步成功: {message}")
                else:
                    self.parent.log(f"❌ 同步失败: {message}")
            
            # 每10次同步更新一次统计
            if self.sync_statistics["total"] % 10 == 0 and self.sync_statistics["total"] > 0:
                success_rate = (self.sync_statistics["success"] / self.sync_statistics["total"]) * 100 if self.sync_statistics["total"] > 0 else 0
                self.parent.log(f"📊 同步统计: 成功率 {success_rate:.1f}% ({self.sync_statistics['success']}/{self.sync_statistics['total']})")
    
    def eventFilter(self, obj, event):
        """事件过滤器，用于捕获窗口事件"""
        try:
            # 只对主要事件类型输出调试信息，避免日志过多
            if event.type() in [QEvent.MouseButtonPress, QEvent.MouseButtonRelease, 
                               QEvent.KeyPress, QEvent.MouseMove]:
                window_title = obj.windowTitle() if hasattr(obj, "windowTitle") else "未知窗口"
                # 避免过多日志，只输出点击和按键事件
                if event.type() == QEvent.MouseButtonPress:
                    self.event_counts["press"] += 1
                    print(f"[事件] 鼠标按下: 来自窗口 '{window_title}'")
                elif event.type() == QEvent.MouseButtonRelease:
                    self.event_counts["release"] += 1
                    # 按下和释放事件计数严重不平衡时输出警告
                    if abs(self.event_counts["press"] - self.event_counts["release"]) > 5:
                        print(f"[警告] 事件计数不平衡: 按下={self.event_counts['press']}, 释放={self.event_counts['release']}")
                elif event.type() == QEvent.KeyPress:
                    self.event_counts["key"] += 1
                    print(f"[事件] 按键: 来自窗口 '{window_title}'")
            
            # 全局事件处理提前捕获 - 任何窗口的点击都尝试检查是否应该添加到监控列表
            if event.type() == QEvent.MouseButtonPress:
                # 检查是否为我们已经监控的窗口
                if obj not in self.monitored_windows and hasattr(obj, "windowTitle"):
                    window_title = obj.windowTitle()
                    if window_title and window_title != "Scrcpy GUI - 安卓屏幕控制":
                        print(f"发现新窗口点击: {window_title}")
                        self.parent.log(f"🆕 发现新窗口: {window_title}")
                        self.parent._force_update_log()
                        
                        # 添加到监控列表
                        obj.installEventFilter(self)
                        self.monitored_windows.append(obj)
                        self.window_titles.append(window_title)
                        self.parent.log(f"✅ 已添加监控: {window_title}")
                        self.parent._force_update_log()
            
            # 监控窗口的事件处理
            if obj in self.monitored_windows:
                window_title = obj.windowTitle() if hasattr(obj, "windowTitle") else "未知窗口"
                
                # 处理不同类型的事件
                if event.type() == QEvent.MouseButtonPress:
                    x, y = event.x(), event.y()
                    button_text = self._get_button_text(event.button())
                    
                    # 记录坐标到日志
                    log_message = f"[事件] 🖱️ {button_text}点击: ({x}, {y}) - 窗口: {window_title}"
                    self.parent.log(log_message)
                    self.parent._force_update_log()  # 强制更新日志
                    print(f"点击事件: {log_message}")  # 控制台输出
                    
                    # 记录点击位置用于拖动计算
                    self.last_touch_pos = (x, y)
                    self.touch_start_time = time.time()
                    
                    # 记录操作
                    self.record_action("tap", (x, y))
                    
                    # 处理点击事件
                    self.handle_mouse_press(event)
                    return False  # 继续传递事件
                    
                elif event.type() == QEvent.MouseButtonRelease:
                    x, y = event.x(), event.y()
                    button_text = self._get_button_text(event.button())
                    release_time = time.time()
                    press_duration = release_time - self.touch_start_time if self.touch_start_time else 0
                    
                    # 判断是否为长按
                    is_long_press = press_duration > 0.8
                    is_drag = self.last_touch_pos and (abs(x - self.last_touch_pos[0]) > 10 or abs(y - self.last_touch_pos[1]) > 10)
                    
                    if is_long_press:
                        log_message = f"[事件] 👇 长按释放: ({x}, {y}) 持续: {press_duration:.2f}秒"
                        action_type = "long_press"
                    elif is_drag:
                        start_x, start_y = self.last_touch_pos
                        log_message = f"[事件] 👉 拖动释放: ({start_x},{start_y}) → ({x},{y})"
                        action_type = "drag"
                    else:
                        log_message = f"[事件] 👆 点击释放: ({x}, {y})"
                        action_type = "tap"
                        
                    self.parent.log(log_message)
                    self.parent._force_update_log()  # 强制更新日志
                    print(f"释放事件: {log_message}")
                    
                    # 处理释放事件
                    self.handle_mouse_release(event)
                    
                    # 重置触摸状态
                    self.last_touch_pos = None
                    self.touch_start_time = None
                    return False  # 继续传递事件
                    
                elif event.type() == QEvent.MouseMove and self.last_touch_pos:
                    x, y = event.x(), event.y()
                    dx = x - self.last_touch_pos[0] 
                    dy = y - self.last_touch_pos[1]
                    
                    # 只在移动距离较大时输出
                    if abs(dx) > 10 or abs(dy) > 10:  # 增大阈值，减少输出
                        log_message = f"[事件] 👉 鼠标移动: ({x}, {y}) 距离: {dx:.0f},{dy:.0f}"
                        self.parent.log(log_message)
                        self.parent._force_update_log()
                        # 减少输出
                        # print(f"移动事件: {log_message}")
                        
                        # 更新位置
                        self.last_touch_pos = (x, y)
                        
                    return False  # 继续传递移动事件
                
                elif event.type() == QEvent.KeyPress:
                    key = event.key()
                    keyText = event.text()
                    log_message = f"[事件] ⌨️ 按键: {key} ('{keyText}')"
                    self.parent.log(log_message)
                    self.parent._force_update_log()
                    print(f"按键事件: {log_message}")
                    
                    self.handle_key_press(event)
                    return False  # 继续传递事件
            
        except Exception as e:
            error_msg = f"事件过滤器错误: {str(e)}"
            self.parent.log(error_msg)
            self.parent._force_update_log()
            print(error_msg)
            import traceback
            traceback.print_exc()
        
        # 继续传递事件
        return False  # 默认继续传递所有事件
        
    def _get_button_text(self, button):
        """将Qt按钮类型转换为文本描述"""
        if button == Qt.LeftButton:
            return "左键"
        elif button == Qt.RightButton:
            return "右键" 
        elif button == Qt.MiddleButton:
            return "中键"
        else:
            return "鼠标"
    
    def handle_mouse_press(self, event):
        """处理鼠标按下事件"""
        try:
            # 检查距离上次事件的间隔
            now = time.time()
            if now - self.last_event_time < self.min_event_interval:
                return False
                
            # 如果正在同步，阻止新的操作
            if self.sync_in_progress:
                self.parent.log("⚠️ 正在处理上一个操作，请稍候...")
                self.parent._force_update_log()
                return False
                
            # 更新事件时间
            self.last_event_time = now
            
            # 获取按钮类型
            button_text = self._get_button_text(event.button())
            x, y = event.x(), event.y()
            
            # 获取窗口信息
            window = event.source() if hasattr(event, "source") and callable(event.source) else None
            window_title = window.windowTitle() if hasattr(window, "windowTitle") else "未知窗口"
            
            # 标记同步开始
            self.sync_in_progress = True
            
            # 同步到其他设备，增加操作前延迟
            if self.slave_device_ids:
                # 发送操作到从设备
                self.parent.log(f"📤 同步{button_text}点击 ({x}, {y}) 到从设备...")
                self.parent._force_update_log()
                
                time.sleep(0.1)  # 轻微延迟，确保界面状态稳定
                result = self.controller.sync_touch_from_main_to_slaves(
                    self.main_device_id, 
                    self.slave_device_ids,
                    x, y, 
                    "tap"
                )
                
                # 处理同步结果
                if result:
                    self.show_sync_feedback(True, f"点击坐标 ({x}, {y})")
                    self.sync_statistics["success"] += 1
                else:
                    self.show_sync_feedback(False, f"点击坐标 ({x}, {y})")
                    self.sync_statistics["failure"] += 1
                
                self.sync_statistics["total"] += 1
            
            # 操作结束
            self.sync_in_progress = False
            return False  # 继续传递事件
            
        except Exception as e:
            self.parent.log(f"处理鼠标按下事件错误: {str(e)}")
            self.parent._force_update_log()
            print(f"处理鼠标按下事件错误: {str(e)}")
            import traceback
            traceback.print_exc()
            self.sync_in_progress = False
            return False
    
    def handle_mouse_release(self, event):
        print("[调试] handle_mouse_release 被调用")
        self.parent.log("[调试] handle_mouse_release 被调用")
        try:
            # 不进行间隔限制，确保释放事件总是被处理
            
            # 如果正在同步，阻止新的操作
            if self.sync_in_progress:
                return
                
            # 检查是否有初始点击位置和时间
            if not self.last_touch_pos or not self.touch_start_time:
                return
                
            # 计算事件类型
            now = time.time()
            press_duration = now - self.touch_start_time
            x, y = event.x(), event.y()
            start_x, start_y = self.last_touch_pos
            
            # 判断事件类型
            is_long_press = press_duration > 0.8
            is_drag = abs(x - start_x) > 10 or abs(y - start_y) > 10
            
            # 获取窗口信息
            window = event.source() if hasattr(event, "source") and callable(event.source) else None
            window_title = window.windowTitle() if hasattr(window, "windowTitle") else "未知窗口"
            
            # 标记同步开始
            self.sync_in_progress = True
            
            # 同步到其他设备
            if self.slave_device_ids:
                if is_long_press:
                    # 发送长按操作
                    self.parent.log(f"📤 同步长按 ({start_x}, {start_y}) 到从设备...")
                    self.parent._force_update_log()
                    
                    result = self.controller.sync_touch_from_main_to_slaves(
                        self.main_device_id, 
                        self.slave_device_ids,
                        start_x, start_y, 
                        "long"
                    )
                    
                elif is_drag:
                    # 发送拖动操作
                    self.parent.log(f"📤 同步拖动 ({start_x}, {start_y}) → ({x}, {y}) 到从设备...")
                    self.parent._force_update_log()
                    
                    result = self.controller.sync_touch_from_main_to_slaves(
                        self.main_device_id, 
                        self.slave_device_ids, 
                        (start_x, start_y, x, y),
                        None,
                        "swipe"
                    )
                else:
                    # 普通点击已在press事件中处理
                    result = True
                
                # 处理同步结果
                if result:
                    action_name = "长按" if is_long_press else ("拖动" if is_drag else "点击")
                    self.show_sync_feedback(True, f"{action_name}操作同步成功")
                    self.sync_statistics["success"] += 1
                else:
                    self.show_sync_feedback(False, f"操作同步失败")
                    self.sync_statistics["failure"] += 1
                
                self.sync_statistics["total"] += 1
            
            # 操作结束
            self.sync_in_progress = False
            
        except Exception as e:
            self.parent.log(f"处理鼠标释放事件错误: {str(e)}")
            self.parent._force_update_log()
            print(f"处理鼠标释放事件错误: {str(e)}")
            import traceback
            traceback.print_exc()
            self.sync_in_progress = False
    
    def handle_mouse_move(self, event):
        """处理鼠标移动事件"""
        # 只有在按下状态才处理移动
        if not self.last_touch_pos:
            return False
            
        # 移动距离太小不处理
        dx = abs(event.x() - self.last_touch_pos[0])
        dy = abs(event.y() - self.last_touch_pos[1])
        
        if dx < 5 and dy < 5:
            return False
            
        # 更新最后位置但不触发事件，等到释放时一次性处理
        self.last_touch_pos = (event.x(), event.y())
        
        return False  # 继续传递事件
    
    def handle_key_press(self, event):
        print("[调试] handle_key_press 被调用")
        self.parent.log("[调试] handle_key_press 被调用")
        if time.time() - self.last_event_time < self.min_event_interval:
            return False
            
        # 如果正在同步，阻止新的操作
        if self.sync_in_progress:
            self.parent.log("⚠️ 正在处理上一个操作，请稍候...")
            return False
            
        self.last_event_time = time.time()
        
        # 记录操作
        self.record_action("key", event.key())
        
        # 标记同步开始
        self.sync_in_progress = True
        
        # 映射按键到Android按键代码
        key_code = self.map_key_to_android_code(event.key())
        if key_code:
            self.parent.log(f"捕获按键事件: {key_code}")
            # 同步按键，增加操作前延迟
            time.sleep(0.1)  # 轻微延迟
            for device_id in self.slave_device_ids:
                self.controller.send_key_event(device_id, key_code)
        
        return False  # 继续传递事件
    
    def map_key_to_android_code(self, key):
        """将Qt按键映射为Android按键代码"""
        # 添加更多按键映射
        key_map = {
            Qt.Key_Home: 3,     # HOME
            Qt.Key_Back: 4,     # BACK
            Qt.Key_Menu: 82,    # MENU
            Qt.Key_VolumeUp: 24,   # VOLUME_UP
            Qt.Key_VolumeDown: 25,  # VOLUME_DOWN
            Qt.Key_Power: 26,   # POWER
            Qt.Key_Enter: 66,   # ENTER
            Qt.Key_Return: 66,  # ENTER
            Qt.Key_Tab: 61,     # TAB
            Qt.Key_Escape: 4,   # BACK
            Qt.Key_Space: 62,   # SPACE
            Qt.Key_Backspace: 67,  # BACKSPACE
            Qt.Key_Left: 21,    # DPAD_LEFT
            Qt.Key_Up: 19,      # DPAD_UP
            Qt.Key_Right: 22,   # DPAD_RIGHT
            Qt.Key_Down: 20,    # DPAD_DOWN
        }
        return key_map.get(key)
    
    def stop_monitoring(self):
        """停止监控"""
        for window in self.monitored_windows:
            if window:
                window.removeEventFilter(self)
        self.monitored_windows.clear()
        
        if hasattr(self, 'find_timer') and self.find_timer.isActive():
            self.find_timer.stop()
        
        self.is_monitoring = False
        self.parent.log("已停止群控事件监控")

class ScrcpyUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.process = QProcess()
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.adb_path = self.find_adb_path()  # 自动查找ADB路径
        self.scrcpy_path = self.find_scrcpy_path()  # 自动查找scrcpy路径
        
        # 设置应用图标
        self.set_application_icon()
        
        # 设备进程字典，用于跟踪多个设备的scrcpy进程
        self.device_processes = {}
        
        # 添加进程跟踪列表，防止进程提前销毁
        self.process_tracking = []
        
        # 添加应用程序退出事件处理
        QApplication.instance().aboutToQuit.connect(self.cleanup_processes)
        
        # 标记应用状态，防止在对象销毁后访问
        self.is_closing = False
        
        # 上次日志消息，用于避免重复
        self.last_log_message = ""
        self.repeat_count = 0
        
        # 创建控制器
        self.controller = ScrcpyController()
        
        # 群控相关变量
        self.sync_control_enabled = False
        self.main_device_id = None  # 主控设备ID
        self.controlled_devices = []  # 被控设备ID列表
        self.event_monitor = None  # 事件监控器
        
        # 应用柔和的中性主题
        self.apply_dark_theme()
        
        self.initUI()
        
        # 检查ADB是否可用
        if not self.check_adb_available():
            QMessageBox.warning(self, "警告", f"ADB路径({self.adb_path})不可用。请检查ADB是否已安装并在环境变量中。")
            self.log(f"警告: ADB路径({self.adb_path})不可用")
        else:
            self.log(f"使用ADB路径: {self.adb_path}")
            
        # 检查scrcpy是否可用
        if not self.check_scrcpy_available():
            QMessageBox.warning(self, "警告", f"scrcpy路径({self.scrcpy_path})不可用。请检查scrcpy是否已安装并在环境变量中。")
            self.log(f"警告: scrcpy路径({self.scrcpy_path})不可用")
        else:
            self.log(f"使用scrcpy路径: {self.scrcpy_path}")
        
        # 初始加载设备列表
        self.check_devices()
        
        # 创建设备检查定时器，但初始状态根据auto_refresh_cb复选框来决定
        self.device_timer = QTimer()
        self.device_timer.timeout.connect(self.check_devices)
        # 定时器将在initUI完成后根据自动刷新复选框状态启动
    
    def cleanup_processes(self):
        """在应用程序关闭前清理所有进程"""
        try:
            # 标记应用正在关闭
            self.is_closing = True
            print("开始清理进程...")
            
            # 停止事件监控
            if hasattr(self, 'event_monitor') and self.event_monitor:
                try:
                    self.event_monitor.stop_monitoring()
                    print("停止事件监控成功")
                except Exception as e:
                    print(f"停止事件监控时出错: {e}")
                self.event_monitor = None
            
            # 停止设备进程
            if hasattr(self, 'device_processes'):
                for device_id, process in list(self.device_processes.items()):
                    try:
                        if process and process.state() == QProcess.Running:
                            print(f"正在终止设备 {device_id} 的进程...")
                            # 断开所有信号连接
                            try:
                                process.disconnect()
                            except Exception:
                                pass
                            
                            process.kill()  # 强制结束进程
                            process.waitForFinished(2000)  # 等待进程结束，增加超时时间
                            print(f"已终止设备 {device_id} 的进程")
                    except Exception as e:
                        print(f"终止设备 {device_id} 进程时出错: {e}")
            
                # 清空进程字典
                self.device_processes.clear()
            
            # 确保进程跟踪列表中的进程也被终止
            if hasattr(self, 'process_tracking'):
                for i, proc in enumerate(self.process_tracking):
                    try:
                        if proc and proc.state() == QProcess.Running:
                            proc.disconnect()
                            proc.kill()
                            proc.waitForFinished(1000)
                            print(f"已终止跟踪进程 #{i}")
                    except Exception as e:
                        print(f"终止跟踪进程 #{i} 时出错: {e}")
                    
                self.process_tracking.clear()
            
            # 确保主进程被终止
            if hasattr(self, 'process') and self.process and self.process.state() == QProcess.Running:
                try:
                    self.process.disconnect()
                    self.process.kill()
                    self.process.waitForFinished(1000)
                except Exception as e:
                    print(f"终止主进程时出错: {e}")
                
            print("所有进程已清理完毕")
        except Exception as e:
            print(f"清理进程时出错: {e}")
        
    def closeEvent(self, event):
        """重写关闭事件，确保进程被正确关闭"""
        self.cleanup_processes()
        super().closeEvent(event)
        
    def log(self, message):
        """向日志文本框中添加消息"""
        if not message:
            return
        
        # 检查应用是否正在关闭    
        if hasattr(self, 'is_closing') and self.is_closing:
            # 在关闭状态仅打印到控制台
            print(f"日志 (应用正在关闭): {message}")
            return
            
        # 检查控件是否有效
        if not hasattr(self, 'log_text') or self.log_text is None or not hasattr(self.log_text, "append"):
            print(f"日志 (控件无效): {message}")  # 控件无效时打印到控制台
            return
            
        try:
            # 添加时间戳
            import datetime
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            
            # 处理重复消息
            if hasattr(self, 'last_log_message') and message == self.last_log_message:
                if hasattr(self, 'repeat_count'):
                    self.repeat_count += 1
                else:
                    self.repeat_count = 1
                    
                # 删除最后一行
                cursor = self.log_text.textCursor()
                cursor.movePosition(cursor.End)
                cursor.movePosition(cursor.StartOfLine, cursor.KeepAnchor)
                cursor.removeSelectedText()
                # 添加带计数的消息
                self.log_text.append(f"[{timestamp}] {message} (x{self.repeat_count})")
            else:
                self.last_log_message = message
                self.repeat_count = 1
                self.log_text.append(f"[{timestamp}] {message}")
            
            # 限制日志行数，防止过长
            max_lines = 500  # 最多保留500行
            text = self.log_text.toPlainText()
            lines = text.split('\n')
            if len(lines) > max_lines:
                # 保留最后max_lines行
                new_text = '\n'.join(lines[-max_lines:])
                self.log_text.setPlainText(new_text)
            
            # 更强制的UI更新措施
            self._force_update_log()
            
            # 打印到控制台，增加调试信息
            print(f"[{timestamp}] {message}")
        except Exception as e:
            print(f"添加日志时出错: {e}, 消息: {message}")

    def _force_update_log(self):
        """强制更新日志UI显示"""
        # 滚动到底部
        scrollbar = self.log_text.verticalScrollBar()
        if scrollbar:
            scrollbar.setValue(scrollbar.maximum())
        
        # 强制UI刷新
        self.log_text.repaint()
        QApplication.processEvents()
        
        # 第二次确保滚动条滚动到底部
        if scrollbar:
            QApplication.processEvents()
            scrollbar.setValue(scrollbar.maximum())
            QApplication.processEvents()
        
    def handle_process_finished(self, device_id):
        """处理进程结束事件"""
        if device_id in self.device_processes:
            del self.device_processes[device_id]
            self.log(f"设备 {device_id} 的进程已结束")
            
    def set_application_icon(self):
        """设置应用程序图标"""
        try:
            # 首先尝试从create_icon模块获取图标字节
            try:
                import create_icon
                import io
                from PyQt5.QtGui import QPixmap
                
                # 从字节直接创建图标
                icon_bytes = create_icon.get_icon_bytes()
                if icon_bytes:
                    pixmap = QPixmap()
                    pixmap.loadFromData(icon_bytes)
                    if not pixmap.isNull():
                        app_icon = QIcon(pixmap)
                        self.setWindowIcon(app_icon)
                        print("已设置内嵌图标")
                        return
            except Exception as e:
                print(f"无法加载内嵌图标: {e}")
                
            # 如果内嵌图标不可用，尝试查找图标文件
            icon_paths = [
                "1.ico",                       # 当前目录
                os.path.join(os.getcwd(), "1.ico"),  # 完整路径
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "1.ico"),  # 脚本目录
                os.path.join(os.path.dirname(sys.executable), "1.ico"),  # 可执行文件目录
            ]
            
            # 尝试加载ICO图标
            for icon_path in icon_paths:
                if os.path.exists(icon_path):
                    try:
                        app_icon = QIcon(icon_path)
                        if not app_icon.isNull():
                            self.setWindowIcon(app_icon)
                            print(f"已设置窗口图标: {icon_path}")
                            return
                    except Exception as e:
                        print(f"加载图标失败: {e}")
            
            print("没有找到有效的图标文件")
            
            # 最后尝试生成一个新的图标
            try:
                import create_icon
                create_icon.create_simple_icon()
                app_icon = QIcon("1.ico")
                self.setWindowIcon(app_icon)
                print("已设置新生成的图标")
            except Exception as e:
                print(f"生成图标失败: {e}")
        
        except Exception as e:
            print(f"设置图标过程中出错: {e}")

    def apply_dark_theme(self):
        """应用柔和的中性主题"""
        palette = QPalette()
        
        # 设置柔和的颜色方案
        background_color = QColor(250, 250, 250)  # 更柔和的白色背景
        text_color = QColor(33, 33, 33)  # 稍深的文字颜色
        highlight_color = QColor(66, 135, 245)  # 蓝色高亮
        secondary_background = QColor(240, 240, 240)  # 次级背景
        
        # 应用颜色到调色板
        palette.setColor(QPalette.Window, background_color)
        palette.setColor(QPalette.WindowText, text_color)
        palette.setColor(QPalette.Base, QColor(255, 255, 255))  # 白色背景
        palette.setColor(QPalette.AlternateBase, secondary_background)
        palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
        palette.setColor(QPalette.ToolTipText, text_color)
        palette.setColor(QPalette.Text, text_color)
        palette.setColor(QPalette.Disabled, QPalette.Text, QColor(150, 150, 150))
        palette.setColor(QPalette.Button, background_color)
        palette.setColor(QPalette.ButtonText, text_color)
        palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(150, 150, 150))
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, highlight_color)
        palette.setColor(QPalette.Highlight, highlight_color)
        palette.setColor(QPalette.HighlightedText, Qt.white)
        
        # 应用调色板
        self.setPalette(palette)
        
        # 设置样式表
        self.setStyleSheet("""
            QGroupBox {
                border: 1px solid #d0d0d0;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 15px;
                font-weight: bold;
                background-color: #f8f8f8;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 5px;
                color: #4287f5;
            }
            QPushButton {
                background-color: #4287f5;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                min-height: 28px;
            }
            QPushButton:hover {
                background-color: #3a75d8;
            }
            QPushButton:pressed {
                background-color: #2b5db8;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #888888;
            }
            QPushButton#usb_btn, QPushButton#wifi_btn {
                background-color: #4CAF50;
            }
            QPushButton#usb_btn:hover, QPushButton#wifi_btn:hover {
                background-color: #45a049;
            }
            QPushButton#usb_btn:pressed, QPushButton#wifi_btn:pressed {
                background-color: #388e3c;
            }
            QPushButton#connect_all_btn {
                background-color: #FF9800;
            }
            QPushButton#connect_all_btn:hover {
                background-color: #F57C00;
            }
            QPushButton#connect_all_btn:pressed {
                background-color: #E65100;
            }
            QPushButton#stop_btn {
                background-color: #f44336;
            }
            QPushButton#stop_btn:hover {
                background-color: #e53935;
            }
            QPushButton#stop_btn:pressed {
                background-color: #d32f2f;
            }
            QPushButton#screenshot_btn {
                background-color: #2196F3;
            }
            QPushButton#screenshot_btn:hover {
                background-color: #1E88E5;
            }
            QPushButton#screenshot_btn:pressed {
                background-color: #1976D2;
            }
            QPushButton#clear_log_btn {
                background-color: #757575;
            }
            QPushButton#clear_log_btn:hover {
                background-color: #616161;
            }
            QPushButton#clear_log_btn:pressed {
                background-color: #424242;
            }
            QLineEdit, QComboBox {
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 6px 10px;
                background-color: white;
                color: #333333;
                min-height: 28px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 20px;
                border-left: 1px solid #d0d0d0;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #d0d0d0;
                background-color: white;
                selection-background-color: #e5e5e5;
                selection-color: #333333;
            }
            QCheckBox {
                color: #333333;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #d0d0d0;
                border-radius: 3px;
                background-color: white;
            }
            QCheckBox::indicator:checked {
                background-color: #4287f5;
                border-color: #4287f5;
            }
            QCheckBox::indicator:hover {
                border-color: #4287f5;
            }
            QTextEdit {
                background-color: white;
                border: 1px solid #d0d0d0;
                color: #333333;
                padding: 5px;
            }
            QScrollBar:vertical {
                border: none;
                background: #f0f0f0;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #c0c0c0;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
    def find_adb_path(self):
        """查找adb路径"""
        try:
            # 检查是否是PyInstaller打包环境
            if getattr(sys, 'frozen', False):
                # 在PyInstaller环境中，使用_MEIPASS查找打包的资源目录
                base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
                adb_path = os.path.join(base_path, 'scrcpy-win64-v3.2', 'adb.exe')
                if os.path.isfile(adb_path):
                    self.log(f"使用打包的adb: {adb_path}")
                    return adb_path
            
            # 首先检查项目目录下的scrcpy-win64-v3.2文件夹中的adb
            local_adb_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                          'scrcpy-win64-v3.2', 'adb.exe')
            if os.path.isfile(local_adb_path):
                self.log(f"使用本地adb: {local_adb_path}")
                return local_adb_path
                
            # 如果本地没有，再检查环境变量
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creationflags = subprocess.CREATE_NO_WINDOW
                result = subprocess.run(['where', 'adb'], 
                                      capture_output=True, 
                                      text=True, 
                                      check=False,
                                      startupinfo=startupinfo,
                                      creationflags=creationflags)
                
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            else:
                # 在Linux和macOS下查找
                result = subprocess.run(['which', 'adb'], 
                                      capture_output=True, 
                                      text=True, 
                                      check=False)
                
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            
            # 如果没有找到，尝试一些常见的路径
            common_paths = [
                os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Android', 'sdk', 'platform-tools', 'adb.exe'),
                os.path.join(os.environ.get('ProgramFiles', ''), 'Android', 'sdk', 'platform-tools', 'adb.exe'),
                os.path.join(os.environ.get('ProgramFiles(x86)', ''), 'Android', 'sdk', 'platform-tools', 'adb.exe'),
                '/usr/bin/adb',
                '/usr/local/bin/adb'
            ]
        
            for path in common_paths:
                if os.path.isfile(path):
                    return path
            
            # 如果仍然没有找到，返回默认的'adb'命令
            return 'adb'
        except Exception as e:
            self.log(f"查找adb路径出错: {e}")
            return 'adb'
        
    def find_scrcpy_path(self):
        """查找scrcpy路径"""
        try:
            # 检查是否是PyInstaller打包环境
            if getattr(sys, 'frozen', False):
                # 在PyInstaller环境中，使用_MEIPASS查找打包的资源目录
                base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
                scrcpy_path = os.path.join(base_path, 'scrcpy-win64-v3.2', 'scrcpy.exe')
                if os.path.isfile(scrcpy_path):
                    self.log(f"使用打包的scrcpy: {scrcpy_path}")
                    return scrcpy_path
            
            # 首先检查项目目录下的scrcpy-win64-v3.2文件夹
            local_scrcpy_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                          'scrcpy-win64-v3.2', 'scrcpy.exe')
            if os.path.isfile(local_scrcpy_path):
                self.log(f"使用本地scrcpy: {local_scrcpy_path}")
                return local_scrcpy_path
                
            # 如果本地没有，才尝试通过环境变量PATH查找
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creationflags = subprocess.CREATE_NO_WINDOW
                # 在Windows下尝试查找
                result = subprocess.run(['where', 'scrcpy'], 
                                       capture_output=True, 
                                       text=True, 
                                       check=False,
                                       startupinfo=startupinfo,
                                       creationflags=creationflags)
                
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            else:
                # 在Linux和macOS下查找
                result = subprocess.run(['which', 'scrcpy'], 
                                       capture_output=True, 
                                       text=True, 
                                       check=False)
                
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            
            # 如果没有找到，尝试一些常见的路径
            common_paths = [
                os.path.join(os.environ.get('LOCALAPPDATA', ''), 'scrcpy', 'scrcpy.exe'),
                os.path.join(os.environ.get('ProgramFiles', ''), 'scrcpy', 'scrcpy.exe'),
                os.path.join(os.environ.get('ProgramFiles(x86)', ''), 'scrcpy', 'scrcpy.exe'),
                '/usr/bin/scrcpy',
                '/usr/local/bin/scrcpy'
            ]
        
            for path in common_paths:
                if os.path.isfile(path):
                    return path
            
            # 如果仍然没有找到，返回默认的'scrcpy'命令
            return 'scrcpy'
        except Exception as e:
            self.log(f"查找scrcpy路径出错: {e}")
            return 'scrcpy'
        
    def check_adb_available(self):
        """检查adb是否可用"""
        try:
            kwargs = {}
            if os.name == 'nt':  # Windows
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            subprocess.run([self.adb_path, "version"], capture_output=True, **kwargs)
            return True
        except:
            return False
            
    def check_scrcpy_available(self):
        """检查scrcpy是否可用"""
        try:
            kwargs = {}
            if os.name == 'nt':  # Windows
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            subprocess.run([self.scrcpy_path, "--version"], capture_output=True, **kwargs)
            return True
        except:
            return False
        
    def initUI(self):
        # 设置窗口
        self.setWindowTitle('Scrcpy GUI - 安卓屏幕控制')
        self.setGeometry(100, 100, 980, 720)  # 增大窗口尺寸
        self.setMinimumSize(800, 600)  # 增大最小尺寸
        
        # 创建菜单栏
        self.create_menus()
        
        # 创建中央部件和主布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)
        
        # 创建设备管理区域
        device_group = QGroupBox("设备连接")
        device_layout = QHBoxLayout(device_group)
        
        # 设备选择区域
        device_label = QLabel("设备:")
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(250)
        
        refresh_btn = QPushButton("刷新设备")
        refresh_btn.clicked.connect(lambda: self.check_devices(True))  # 显式传递show_message=True
        
        device_layout.addWidget(device_label)
        device_layout.addWidget(self.device_combo, 1)
        device_layout.addWidget(refresh_btn)
        
        # 添加连接类型选项
        self.usb_btn = QPushButton("一键USB连接")
        self.usb_btn.clicked.connect(self.start_scrcpy)
        self.usb_btn.setObjectName("usb_btn")
        
        self.wifi_btn = QPushButton("一键WIFI连接")
        self.wifi_btn.clicked.connect(self.connect_wireless)
        self.wifi_btn.setObjectName("wifi_btn")
        
        self.connect_all_btn = QPushButton("连接所有设备")
        self.connect_all_btn.clicked.connect(self.connect_all_devices)
        self.connect_all_btn.setObjectName("connect_all_btn")
        
        # 自动刷新选项
        self.auto_refresh_cb = QCheckBox("自动刷新")
        self.auto_refresh_cb.setChecked(False)  # 默认不自动刷新
        self.auto_refresh_cb.stateChanged.connect(self.toggle_auto_refresh)
        
        connection_layout = QHBoxLayout()
        connection_layout.addWidget(self.usb_btn)
        connection_layout.addWidget(self.wifi_btn)
        connection_layout.addWidget(self.connect_all_btn)
        connection_layout.addStretch(1)
        connection_layout.addWidget(self.auto_refresh_cb)
        
        # 添加连接布局到设备组
        device_layout.addLayout(connection_layout)
        
        # 添加镜像模式选项组
        mirror_group = QGroupBox("镜像模式")
        mirror_layout = QGridLayout(mirror_group)
        
        # 比特率
        bitrate_label = QLabel("比特率:")
        self.bitrate_input = QLineEdit("6")
        self.bitrate_input.setMaximumWidth(80)
        bitrate_unit = QLabel("Mbps")
        
        # 最大尺寸
        maxsize_label = QLabel("最大尺寸:")
        self.maxsize_input = QLineEdit("1080")
        self.maxsize_input.setMaximumWidth(80)
        
        # 录制格式
        format_label = QLabel("录制格式:")
        self.format_combo = QComboBox()
        self.format_combo.addItems(["mp4", "mkv"])
        self.format_combo.setMaximumWidth(100)
        
        # 限制方向
        rotation_label = QLabel("限制方向:")
        self.rotation_combo = QComboBox()
        self.rotation_combo.addItems(["不限制", "横屏", "竖屏"])
        self.rotation_combo.setMaximumWidth(100)
        
        # 录制存储路径
        record_label = QLabel("录制存储路径:")
        self.record_path = QLineEdit()
        self.record_path.setPlaceholderText("默认不录制")
        
        browse_btn = QPushButton("选择路径")
        browse_btn.clicked.connect(self.select_record_path)
        
        # 添加控件到布局
        mirror_layout.addWidget(bitrate_label, 0, 0)
        mirror_layout.addWidget(self.bitrate_input, 0, 1)
        mirror_layout.addWidget(bitrate_unit, 0, 2)
        mirror_layout.addWidget(maxsize_label, 0, 3)
        mirror_layout.addWidget(self.maxsize_input, 0, 4)
        mirror_layout.addWidget(format_label, 1, 0)
        mirror_layout.addWidget(self.format_combo, 1, 1)
        mirror_layout.addWidget(rotation_label, 1, 3)
        mirror_layout.addWidget(self.rotation_combo, 1, 4)
        mirror_layout.addWidget(record_label, 2, 0)
        mirror_layout.addWidget(self.record_path, 2, 1, 1, 4)
        mirror_layout.addWidget(browse_btn, 2, 5)
        
        # 添加功能选项组
        options_group = QGroupBox("功能选项")
        options_layout = QGridLayout(options_group)
        
        self.record_cb = QCheckBox("录制屏幕")
        self.fullscreen_cb = QCheckBox("全屏显示")
        self.always_top_cb = QCheckBox("窗口置顶")
        self.show_touches_cb = QCheckBox("显示触摸")
        self.no_control_cb = QCheckBox("无交互")
        self.disable_clipboard_cb = QCheckBox("禁用剪贴板")
        
        # 添加同步群控选项
        self.sync_control_cb = QCheckBox("同步群控")
        self.sync_control_cb.setToolTip("开启后，对主控设备的操作将同步到其他设备")
        self.sync_control_cb.stateChanged.connect(self.toggle_sync_control)
        
        self.sync_control_device_combo = QComboBox()
        self.sync_control_device_combo.setEnabled(False)
        self.sync_control_device_combo.setToolTip("选择主控设备")
        self.sync_control_device_combo.setMinimumWidth(150)
        
        # 创建群控设置按钮
        self.sync_control_settings_btn = QPushButton("群控设置")
        self.sync_control_settings_btn.clicked.connect(self.show_sync_control_settings)
        self.sync_control_settings_btn.setEnabled(False)
        
        options_layout.addWidget(self.record_cb, 0, 0)
        options_layout.addWidget(self.fullscreen_cb, 0, 1)
        options_layout.addWidget(self.always_top_cb, 0, 2)
        options_layout.addWidget(self.show_touches_cb, 1, 0)
        options_layout.addWidget(self.no_control_cb, 1, 1)
        options_layout.addWidget(self.disable_clipboard_cb, 1, 2)
        
        # 添加群控选项到新的一行
        sync_layout = QHBoxLayout()
        sync_layout.addWidget(self.sync_control_cb)
        sync_layout.addWidget(QLabel("主控设备:"))
        sync_layout.addWidget(self.sync_control_device_combo)
        sync_layout.addWidget(self.sync_control_settings_btn)
        sync_layout.addStretch(1)
        
        options_layout.addLayout(sync_layout, 2, 0, 1, 3)
        
        # 日志区域
        log_group = QGroupBox("操作日志")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        
        log_btns_layout = QHBoxLayout()
        
        clear_log_btn = QPushButton("清空日志")
        clear_log_btn.clicked.connect(self.clear_log)
        clear_log_btn.setObjectName("clear_log_btn")
        
        stop_btn = QPushButton("停止投屏")
        stop_btn.clicked.connect(self.stop_scrcpy)
        stop_btn.setObjectName("stop_btn")
        
        screenshot_btn = QPushButton("截图")
        screenshot_btn.clicked.connect(self.take_screenshot)
        screenshot_btn.setObjectName("screenshot_btn")
        
        log_btns_layout.addWidget(clear_log_btn)
        log_btns_layout.addWidget(stop_btn)
        log_btns_layout.addWidget(screenshot_btn)
        
        log_layout.addWidget(self.log_text)
        log_layout.addLayout(log_btns_layout)
        
        # 添加各个区域到主布局
        main_layout.addWidget(device_group)
        main_layout.addWidget(mirror_group)
        main_layout.addWidget(options_group)
        main_layout.addWidget(log_group, 1)
        
        # 根据自动刷新复选框的初始状态设置定时器
        self.toggle_auto_refresh(Qt.Unchecked)  # 默认不自动刷新
        
    def toggle_auto_refresh(self, state):
        """切换设备列表自动刷新状态"""
        if state == Qt.Checked:
            # 启用自动刷新
            if hasattr(self, 'device_timer'):
                self.device_timer.start(3000)  # 每3秒刷新一次
                self.log("✅ 已启用设备列表自动刷新")
        else:
            # 禁用自动刷新
            if hasattr(self, 'device_timer') and self.device_timer.isActive():
                self.device_timer.stop()
                self.log("❌ 已禁用设备列表自动刷新")
        
        # 强制执行一次设备刷新，并显示消息
        self.check_devices(show_message=True)
    
    def create_menus(self):
        """创建菜单栏"""
        menu_bar = self.menuBar()
        
        # 设备菜单
        device_menu = menu_bar.addMenu("设备")
        
        refresh_action = QAction("刷新设备列表", self)
        refresh_action.triggered.connect(lambda: self.check_devices(True))  # 显示消息
        device_menu.addAction(refresh_action)
        
        device_menu.addSeparator()
        
        connect_usb_action = QAction("USB连接", self)
        connect_usb_action.triggered.connect(self.start_scrcpy)
        device_menu.addAction(connect_usb_action)
        
        connect_wifi_action = QAction("WIFI连接", self)
        connect_wifi_action.triggered.connect(self.connect_wireless)
        device_menu.addAction(connect_wifi_action)
        
        device_menu.addSeparator()
        
        disconnect_action = QAction("断开连接", self)
        disconnect_action.triggered.connect(self.stop_scrcpy)
        device_menu.addAction(disconnect_action)
        
        # 工具菜单
        tools_menu = menu_bar.addMenu("工具")
        
        screenshot_action = QAction("截图", self)
        screenshot_action.triggered.connect(self.take_screenshot)
        tools_menu.addAction(screenshot_action)
        
        # 添加应用管理器入口到工具菜单
        app_manager_action = QAction("应用管理器", self)
        app_manager_action.triggered.connect(self.show_app_manager)
        tools_menu.addAction(app_manager_action)
        
        # 添加群控功能到工具菜单
        tools_menu.addSeparator()
        sync_control_action = QAction("同步群控设置", self)
        sync_control_action.triggered.connect(self.show_sync_control_settings)
        tools_menu.addAction(sync_control_action)
        
        # 帮助菜单
        help_menu = menu_bar.addMenu("帮助")
        
        about_action = QAction("关于", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
    def select_record_path(self):
        """选择录制文件保存路径"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "选择保存位置", "", 
            f"视频文件 (*.{self.format_combo.currentText()})"
        )
        if filename:
            self.record_path.setText(filename)
            
    def clear_log(self):
        """清空日志文本框"""
        self.log_text.clear()
            
    def check_devices(self, show_message=False):
        """检查连接的设备并更新设备列表
        
        Args:
            show_message: 是否显示设备检测消息，默认为False
        """
        try:
            devices = self.controller.get_devices()
            
            # 清空当前列表
            self.device_combo.clear()
            self.sync_control_device_combo.clear()  # 清空群控设备列表
            
            for device_id, model in devices:
                self.device_combo.addItem(f"{model} ({device_id})", device_id)
                self.sync_control_device_combo.addItem(f"{model} ({device_id})", device_id)
            
            # 更新连接按钮状态
            has_devices = self.device_combo.count() > 0
            self.usb_btn.setEnabled(has_devices)
            self.wifi_btn.setEnabled(has_devices)
            self.connect_all_btn.setEnabled(has_devices and len(devices) > 1)
            
            # 更新群控相关控件状态
            self.sync_control_device_combo.setEnabled(has_devices and self.sync_control_cb.isChecked())
            self.sync_control_settings_btn.setEnabled(has_devices and self.sync_control_cb.isChecked())
            
            # 只有当show_message为True或自动刷新开启时才显示无设备消息
            if not has_devices and (show_message or (hasattr(self, 'auto_refresh_cb') and self.auto_refresh_cb.isChecked())):
                self.log("未检测到设备，请检查设备连接")
            elif has_devices and not self.device_combo.currentText() and show_message:
                self.device_combo.setCurrentIndex(0)
                self.sync_control_device_combo.setCurrentIndex(0)
                self.log(f"检测到 {len(devices)} 个设备")
                
                # 如果群控已启用但没有主控设备，则设置当前选择为主控设备
                if self.sync_control_enabled and not self.main_device_id:
                    self.set_main_control_device()
            
            return devices
        except Exception as e:
            if show_message:
                self.log(f"检查设备出错: {e}")
            return []
        
    def start_scrcpy(self):
        """启动scrcpy进程"""
        # 检查是否选择了设备
        if self.device_combo.currentIndex() < 0:
            QMessageBox.warning(self, "警告", "请先选择一个设备")
            return
            
        # 获取当前选择的设备ID
        device_id = self.device_combo.currentData()
        if not device_id:
            QMessageBox.warning(self, "警告", "无效的设备ID")
            return
            
        # 检查设备是否已经连接
        if device_id in self.device_processes and self.device_processes[device_id].state() == QProcess.Running:
            self.log(f"设备 {device_id} 已经在运行")
            return
            
        # 构建命令参数
        cmd = [self.scrcpy_path]
        cmd.extend(['-s', device_id])
        
        # 添加比特率参数
        if self.bitrate_input.text():
            try:
                bitrate = int(self.bitrate_input.text())
                cmd.extend(['--video-bit-rate', f'{bitrate}M'])
            except ValueError:
                self.log("错误: 比特率必须是数字")
                return
                
        # 添加最大尺寸参数
        if self.maxsize_input.text():
            try:
                maxsize = int(self.maxsize_input.text())
                cmd.extend(['--max-size', str(maxsize)])
            except ValueError:
                self.log("错误: 最大尺寸必须是数字")
                return
                
        # 检查是否录制
        if self.record_cb.isChecked():
            # 检查是否提供了录制路径
            if self.record_path.text():
                record_file = self.record_path.text()
                # 确保文件扩展名与选择的格式匹配
                format_ext = self.format_combo.currentText()
                if not record_file.endswith(f".{format_ext}"):
                    record_file = f"{record_file}.{format_ext}"
                cmd.extend(['--record', record_file])
            else:
                QMessageBox.warning(self, "警告", "请提供录制文件保存路径")
                return
                
        # 添加其他选项
        if self.fullscreen_cb.isChecked():
            cmd.append('--fullscreen')
            
        if self.always_top_cb.isChecked():
            cmd.append('--always-on-top')
            
        if self.show_touches_cb.isChecked():
            cmd.append('--show-touches')
            
        if self.no_control_cb.isChecked():
            cmd.append('--no-control')
            
        if self.disable_clipboard_cb.isChecked():
            cmd.append('--no-clipboard-autosync')
            
        # 添加方向控制
        rotation_option = self.rotation_combo.currentText()
        if rotation_option == "横屏":
            cmd.append('--lock-video-orientation=0')
        elif rotation_option == "竖屏":
            cmd.append('--lock-video-orientation=1')
            
        # 设置窗口标题为设备型号，并包含设备ID便于识别
        device_model = self.device_combo.currentText().split(' (')[0]
        window_title = f"{device_model} - {device_id}"
        cmd.extend(['--window-title', window_title])
        
        # 添加触摸反馈效果 - 增强用户体验
        cmd.append('--show-touches')
        
        # 确保窗口可以被移动 - 修复参数错误
        # 默认有边框，所以不需要设置此选项
        # 如果要无边框，使用 --window-borderless (无参数)
        
        # 添加窗口位置参数，避免窗口出现在屏幕边缘
        cmd.extend(['--window-x', '100'])
        cmd.extend(['--window-y', '100'])
        
        # 启动进程
        self.log(f"启动设备 {device_id} 镜像: {' '.join(cmd)}")
        
        try:
            # 创建进程
            process = QProcess()
            
            # 确保进程不会被过早销毁
            self.process_tracking.append(process)
            
            # 连接信号
            process.readyReadStandardOutput.connect(lambda proc=process, dev=device_id: self.handle_process_output(proc, dev))
            process.readyReadStandardError.connect(lambda proc=process, dev=device_id: self.handle_process_error(proc, dev))
            
            # 使用新方式连接finished信号，避免lambda导致的问题
            process.finished.connect(self.create_process_finished_handler(device_id))
            
            # 保存进程
            self.device_processes[device_id] = process
            
            # 启动进程
            process.start(cmd[0], cmd[1:])
            self.log(f"已启动设备 {device_id} 的 scrcpy 进程")
            
            # 不再自动启用事件监控，而是提示用户可以手动开启
            if not self.sync_control_cb.isChecked():
                # 延迟一会再显示提示，确保窗口能正常显示
                QTimer.singleShot(2000, lambda: self.ask_enable_monitoring(device_id))
                
        except Exception as e:
            self.log(f"启动 scrcpy 失败: {str(e)}")
            if device_id in self.device_processes:
                del self.device_processes[device_id]
                
    def ask_enable_monitoring(self, device_id):
        """处理单设备事件监控（已废弃，自动监控，无需提示）"""
        pass
    
    def create_process_finished_handler(self, device_id):
        """创建一个进程结束处理函数，避免lambda表达式可能导致的问题"""
        def handler(exit_code, exit_status):
            try:
                # 从字典中移除设备
                if device_id in self.device_processes:
                    del self.device_processes[device_id]
                    
                # 记录完成事件
                self.log(f"设备 {device_id} 的进程已结束 (退出码: {exit_code})")
                
                # 如果是主控设备，处理群控相关逻辑
                if self.sync_control_enabled and device_id == self.main_device_id:
                    self.log("主控设备已断开连接，停止群控功能")
                    self.sync_control_cb.setChecked(False)
            except Exception as e:
                print(f"处理进程完成事件出错: {str(e)}")
        return handler
    
    def stop_scrcpy(self):
        """停止scrcpy进程"""
        # 如果没有选择设备，停止所有进程
        if self.device_combo.currentIndex() < 0:
            # 先停止事件监控器
            if self.event_monitor:
                self.event_monitor.stop_monitoring()
                self.event_monitor = None
                
            for device_id, process in list(self.device_processes.items()):
                if process.state() == QProcess.Running:
                    process.kill()
                    self.log(f"已停止设备 {device_id} 的 scrcpy 进程")
                    
            self.device_processes.clear()
        else:
            # 获取当前选择的设备ID
            device_id = self.device_combo.currentData()
            if device_id and device_id in self.device_processes:
                process = self.device_processes[device_id]
                if process.state() == QProcess.Running:
                    process.kill()
                    self.log(f"已停止设备 {device_id} 的 scrcpy 进程")
                del self.device_processes[device_id]
                
                # 如果是主控设备，停止事件监控
                if self.event_monitor and device_id == self.main_device_id:
                    self.event_monitor.stop_monitoring()
                    self.event_monitor = None
    
    def handle_process_output(self, process, device_id):
        """处理指定进程的标准输出"""
        data = process.readAllStandardOutput().data().decode('utf-8')
        if data.strip():
            self.log(f"[{device_id}] {data.strip()}")
            
    def handle_process_error(self, process, device_id):
        """处理指定进程的标准错误"""
        data = process.readAllStandardError().data().decode('utf-8')
        if data.strip():
            self.log(f"[{device_id}] 错误: {data.strip()}")
            
    def handle_process_finished(self, device_id):
        """处理进程结束事件"""
        if device_id in self.device_processes:
            del self.device_processes[device_id]
            self.log(f"设备 {device_id} 的进程已结束")
            
    def connect_wireless(self):
        """通过无线方式连接设备"""
        # 检查是否选择了设备
        if self.device_combo.currentIndex() < 0:
            QMessageBox.warning(self, "警告", "请先选择一个设备")
            return
            
        # 获取当前选择的设备ID
        device_id = self.device_combo.currentData()
        if not device_id:
            QMessageBox.warning(self, "警告", "无效的设备ID")
            return
            
        # 使用通用进程进行操作
        temp_process = QProcess()
        
        # 先确保设备处于 TCP/IP 模式
        self.log(f"正在将设备 {device_id} 切换到 TCP/IP 模式...")
        temp_process.start(self.adb_path, ['-s', device_id, 'tcpip', '5555'])
        temp_process.waitForFinished()
        
        if temp_process.exitCode() != 0:
            error = temp_process.readAllStandardError().data().decode('utf-8')
            self.log(f"切换到 TCP/IP 模式失败: {error}")
            return
            
        # 获取设备 IP 地址
        self.log("正在获取设备 IP 地址...")
        temp_process.start(self.adb_path, ['-s', device_id, 'shell', 'ip', 'route'])
        temp_process.waitForFinished()
        
        if temp_process.exitCode() != 0:
            error = temp_process.readAllStandardError().data().decode('utf-8')
            self.log(f"获取 IP 地址失败: {error}")
            return
            
        output = temp_process.readAllStandardOutput().data().decode('utf-8')
        ip_address = None
        
        # 解析 IP 地址
        for line in output.strip().split('\n'):
            if "wlan0" in line and "src" in line:
                parts = line.split()
                ip_index = parts.index("src")
                if ip_index + 1 < len(parts):
                    ip_address = parts[ip_index + 1]
                    break
                    
        if not ip_address:
            self.log("无法获取设备 IP 地址，请确保设备已连接到WiFi")
            return
            
        # 等待几秒让设备准备好
        self.log(f"已找到设备 IP: {ip_address}，等待设备准备就绪...")
        QTimer.singleShot(2000, lambda: self.do_connect_wireless(ip_address, device_id))
        
    def do_connect_wireless(self, ip_address, original_device_id=None):
        """实际执行无线连接"""
        # 使用通用进程进行操作
        temp_process = QProcess()
        
        # 连接到设备
        self.log(f"正在连接到 {ip_address}:5555...")
        temp_process.start(self.adb_path, ['connect', f"{ip_address}:5555"])
        temp_process.waitForFinished()
        
        output = temp_process.readAllStandardOutput().data().decode('utf-8')
        if "connected" in output.lower():
            self.log(f"已成功连接到 {ip_address}:5555")
            
            # 刷新设备列表
            QTimer.singleShot(1000, self.check_devices)
            
            # 启动 scrcpy
            QTimer.singleShot(2000, lambda: self.start_scrcpy_with_ip(ip_address, original_device_id))
        else:
            error = temp_process.readAllStandardError().data().decode('utf-8')
            self.log(f"连接失败: {output} {error}")
            
    def start_scrcpy_with_ip(self, ip_address, original_device_id=None):
        """使用指定的IP地址启动scrcpy"""
        # 更新设备列表
        devices = self.controller.get_devices()
        wireless_device_id = None
        
        # 查找匹配IP地址的设备
        for device_id, _ in devices:
            if device_id.startswith(ip_address):
                wireless_device_id = device_id
                # 移除旧的设备进程
                if original_device_id and original_device_id in self.device_processes:
                    if self.device_processes[original_device_id].state() == QProcess.Running:
                        self.device_processes[original_device_id].kill()
                    del self.device_processes[original_device_id]
                break
        
        if wireless_device_id:
            # 更新设备下拉框选择
            for i in range(self.device_combo.count()):
                if wireless_device_id in self.device_combo.itemText(i):
                    self.device_combo.setCurrentIndex(i)
                    break
            
            # 启动 scrcpy
            self.start_scrcpy()
        else:
            self.log(f"无法找到无线连接的设备 {ip_address}")
            
    def handle_stdout(self):
        """处理标准输出"""
        data = self.process.readAllStandardOutput().data().decode('utf-8')
        if data.strip():
            self.log(data.strip())
            
    def handle_stderr(self):
        """处理标准错误"""
        data = self.process.readAllStandardError().data().decode('utf-8')
        if data.strip():
            self.log(f"错误: {data.strip()}")
    
    def take_screenshot(self):
        """截取设备屏幕并保存到电脑"""
        # 检查是否选择了设备
        if self.device_combo.currentIndex() < 0:
            # 如果有多个设备连接但没有选择，询问是否要截图所有设备
            if len(self.device_processes) > 0:
                reply = QMessageBox.question(
                    self, "截取多个设备", "是否要截取所有已连接设备的屏幕？",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    self.take_all_screenshots()
                    return
            else:
                QMessageBox.warning(self, "警告", "请先选择一个设备")
            return
        
        # 获取当前选择的设备ID
        device_id = self.device_combo.currentData()
        if not device_id:
            QMessageBox.warning(self, "警告", "无效的设备ID")
            return
        
        # 获取设备型号
        device_model = self.device_combo.currentText().split(' (')[0]
        
        # 打开文件保存对话框
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"screenshot_{device_model}_{timestamp}.png"
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "保存截图", default_filename, "图片文件 (*.png)"
        )
        
        if not filename:
            return  # 用户取消了保存操作
            
        # 使用控制器获取截图
        success, message = self.controller.capture_screenshot(device_id, filename)
        
        if success:
            self.log(f"设备 {device_model} ({device_id}) 截图已保存至 {filename}")
            # 询问是否要查看截图
            reply = QMessageBox.question(
                self, "查看截图", "截图已保存，是否立即查看？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # 使用系统默认程序打开图片
                if os.name == 'nt':  # Windows
                    os.startfile(filename)
                elif os.name == 'posix':  # Linux/macOS
                    kwargs = {}
                    subprocess.run(['xdg-open', filename], check=False, **kwargs)
        else:
            self.log(f"截图失败: {message}")
            
    def take_all_screenshots(self):
        """截取所有已连接设备的屏幕"""
        if not self.device_processes:
            QMessageBox.warning(self, "警告", "没有连接的设备")
            return
            
        # 询问保存位置
        save_dir = QFileDialog.getExistingDirectory(self, "选择保存目录", "")
        if not save_dir:
            return  # 用户取消了操作
            
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        success_count = 0
        for device_id in self.device_processes.keys():
            # 获取设备信息
            device_model = "未知设备"
            for i in range(self.device_combo.count()):
                if device_id in self.device_combo.itemText(i):
                    device_model = self.device_combo.itemText(i).split(' (')[0]
                    break
                    
            # 生成文件名
            filename = os.path.join(save_dir, f"screenshot_{device_model}_{device_id}_{timestamp}.png")
            
            # 截图
            success, message = self.controller.capture_screenshot(device_id, filename)
            
            if success:
                self.log(f"设备 {device_model} ({device_id}) 截图已保存至 {filename}")
                success_count += 1
            else:
                self.log(f"截取设备 {device_model} ({device_id}) 失败: {message}")
                
        if success_count > 0:
            # 询问是否要打开保存目录
            reply = QMessageBox.question(
                self, "查看截图", f"成功保存 {success_count} 张截图，是否打开保存目录？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # 打开保存目录
                if os.name == 'nt':  # Windows
                    os.startfile(save_dir)
                elif os.name == 'posix':  # Linux/macOS
                    kwargs = {}
                    subprocess.run(['xdg-open', save_dir], check=False, **kwargs)
            
    def connect_all_devices(self):
        """连接所有检测到的设备"""
        devices = self.controller.get_devices()
        if not devices:
            QMessageBox.warning(self, "警告", "未检测到设备")
            return
            
        # 询问用户是否要先停止所有当前运行的设备进程
        if self.device_processes:
            reply = QMessageBox.question(
                self, "已有设备运行", "是否先停止当前所有设备进程？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                self.stop_scrcpy()  # 停止所有当前设备进程
        
        count = 0
        device_count = len(devices)
        
        # 如果设备超过1个，询问用户是否以轻量模式运行
        lite_mode = False
        if device_count > 1:
            reply = QMessageBox.question(
                self, "多设备连接模式", "多设备连接可能会占用较大系统资源，是否以轻量模式运行？\n(低分辨率、低比特率)",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
            )
            lite_mode = (reply == QMessageBox.Yes)
        
        # 保存已启动的设备ID列表
        started_devices = []
        
        for device_id, model in devices:
            # 检查设备是否已经连接
            if device_id in self.device_processes and self.device_processes[device_id].state() == QProcess.Running:
                self.log(f"设备 {model} ({device_id}) 已经在运行")
                continue
                
            # 构建命令参数
            cmd = [self.scrcpy_path]
            cmd.extend(['-s', device_id])
            
            # 轻量模式下使用更低的设置
            if lite_mode:
                cmd.extend(['--max-size', '800'])
                cmd.extend(['--video-bit-rate', '2M'])
                cmd.extend(['--max-fps', '25'])
            else:
                # 添加最大尺寸参数
                try:
                    maxsize = int(self.maxsize_input.text()) if self.maxsize_input.text() else 1080
                    cmd.extend(['--max-size', str(maxsize)])
                except ValueError:
                    cmd.extend(['--max-size', '1080'])
                
                # 添加比特率参数
                if self.bitrate_input.text():
                    try:
                        bitrate = int(self.bitrate_input.text())
                        cmd.extend(['--video-bit-rate', f'{bitrate}M'])
                    except ValueError:
                        cmd.extend(['--video-bit-rate', '4M'])
            
            # 添加窗口标题，包含设备信息以便识别
            window_title = f"Scrcpy - {model} ({device_id})"
            cmd.extend(['--window-title', window_title])
            
            # 添加窗口位置偏移，避免所有窗口重叠
            columns = max(1, int(math.sqrt(device_count)))  # 根据设备数量计算合适的列数
            row = count // columns
            col = count % columns
            
            # 给窗口留出更大间距，避免完全重叠
            x_offset = col * 400  # 增加水平间距到400像素
            y_offset = row * 300  # 增加垂直间距到300像素
            
            # 添加--window-x和--window-y参数设置初始位置
            cmd.extend(['--window-x', str(x_offset + 100)])  # 增加初始边距
            cmd.extend(['--window-y', str(y_offset + 100)])
            
            # 添加触摸反馈效果 - 增强用户体验
            cmd.append('--show-touches')
            
            # 确保窗口可以被移动 - 修复参数错误
            # 默认有边框，所以不需要设置此选项
            # 如果要无边框，使用 --window-borderless (无参数)
            
            # 窗口置顶
            cmd.append('--always-on-top')
            
            try:
                # 创建进程
                process = QProcess()
                
                # 确保进程不被过早销毁
                self.process_tracking.append(process)
                
                # 连接信号
                process.readyReadStandardOutput.connect(lambda proc=process, dev=device_id: self.handle_process_output(proc, dev))
                process.readyReadStandardError.connect(lambda proc=process, dev=device_id: self.handle_process_error(proc, dev))
                
                # 使用新方式连接finished信号，避免lambda导致的参数传递问题
                process.finished.connect(self.create_process_finished_handler(device_id))
                
                # 保存进程
                self.device_processes[device_id] = process
                
                # 启动进程
                process.start(cmd[0], cmd[1:])
                self.log(f"已启动设备 {model} ({device_id}) 的 scrcpy 进程")
                started_devices.append(device_id)
                count += 1
                
                # 每个设备启动后稍微等待一下，避免系统资源争用
                if count < len(devices):
                    time.sleep(1.5)  # 增加等待时间到1.5秒
                
            except Exception as e:
                self.log(f"启动设备 {model} ({device_id}) 失败: {str(e)}")
                if device_id in self.device_processes:
                    del self.device_processes[device_id]
                    
        if count > 0:
            self.log(f"成功连接 {count} 个设备")
            
            # 不再自动勾选同步群控，只提供提示信息
            if count > 1:
                self.log("📱 已连接多个设备，可以手动开启同步群控功能")
                
            # 提示用户如何移动窗口
            if count > 1:
                # 显示提示信息，不使用弹窗
                self.log("💡 多设备连接提示:")
                self.log("1️⃣ 可拖动窗口标题栏移动窗口位置")
                self.log("2️⃣ 使用Alt+左键可调整窗口大小") 
                self.log("3️⃣ 窗口已自动置顶，便于操作")
                self.log("4️⃣ 鼠标右键可返回上一步")
    
    def show_about(self):
        """显示关于对话框"""
        about_text = "Scrcpy GUI\n\n"
        about_text += "一个基于scrcpy的Android设备镜像和控制工具。\n\n"
        about_text += "支持多设备连接、WIFI连接、屏幕录制等功能。\n"
        about_text += "支持截图功能。\n\n"
        
        QMessageBox.about(self, "关于Scrcpy GUI", about_text)

    def show_app_manager(self):
        """显示应用管理器对话框"""
        # 获取当前选择的设备ID
        device_id = None
        if self.device_combo.currentIndex() >= 0:
            device_id = self.device_combo.currentData()
            
        # 创建应用管理器对话框
        app_manager = AppManagerDialog(self, self.controller)
        app_manager.exec_()

    # 添加群控相关方法
    def toggle_sync_control(self, state):
        """开启或关闭同步群控功能"""
        self.sync_control_enabled = (state == Qt.Checked)
        self.sync_control_device_combo.setEnabled(self.sync_control_enabled)
        self.sync_control_settings_btn.setEnabled(self.sync_control_enabled)
        
        if self.sync_control_enabled:
            # 开启群控时，设置主控设备
            self.set_main_control_device()
            self.log("已开启同步群控功能，选择一个主控设备")
            
            # 检查设备状态，但允许单个设备也能使用监控功能
            if len(self.device_processes) < 2:
                self.log("当前只有一个设备，将启用单设备监控模式")
            
            # 添加调试信息
            active_windows = [w.windowTitle() for w in QApplication.topLevelWidgets() 
                             if hasattr(w, "windowTitle") and w.windowTitle()]
            self.log(f"当前活动窗口数量: {len(active_windows)}")
            for i, title in enumerate(active_windows[:5]):  # 仅显示前5个窗口
                self.log(f"窗口 #{i+1}: {title}")
        else:
            # 关闭群控
            self.main_device_id = None
            self.controlled_devices = []
            self.log("已关闭同步群控功能")
            
            # 停止事件监控器
            if hasattr(self, 'event_monitor') and self.event_monitor:
                self.event_monitor.stop_monitoring()
                self.event_monitor = None
                self.log("已停止事件监控")
    
    def set_main_control_device(self):
        """设置主控设备"""
        if self.sync_control_device_combo.currentIndex() >= 0:
            self.main_device_id = self.sync_control_device_combo.currentData()
            self.controlled_devices = []
            
            # 获取所有已连接设备，除了主控设备
            for device_id in self.device_processes.keys():
                if device_id != self.main_device_id:
                    self.controlled_devices.append(device_id)
            
            if self.main_device_id:
                self.log(f"已设置设备 {self.main_device_id} 为主控设备")
                
                # 显示窗口处理相关日志
                for device_id in [self.main_device_id] + self.controlled_devices:
                    info = self.controller.get_device_full_info(device_id)
                    device_name = f"{info['brand']} {info['model']}"
                    process = self.device_processes.get(device_id)
                    if process and process.state() == QProcess.Running:
                        self.log(f"检查设备 {device_name} 的窗口...")
            
            # 监听主控设备事件
            self.setup_event_listeners()
    
    def show_sync_control_settings(self):
        """显示群控设置对话框"""
        if not self.sync_control_enabled:
            reply = QMessageBox.question(
                self, "同步群控", "是否开启同步群控功能？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.sync_control_cb.setChecked(True)
                
                if len(self.device_processes) < 2:
                    QMessageBox.information(self, "群控提示", "请先连接多个设备以使用群控功能")
                    return
            else:
                return
                
        # 创建群控设置对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("同步群控设置")
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout(dialog)
        
        # 选择主控设备
        main_device_layout = QHBoxLayout()
        main_device_layout.addWidget(QLabel("主控设备:"))
        main_device_combo = QComboBox()
        
        # 填充设备列表
        for i in range(self.sync_control_device_combo.count()):
            main_device_combo.addItem(
                self.sync_control_device_combo.itemText(i),
                self.sync_control_device_combo.itemData(i)
            )
        
        # 设置当前选中的主控设备
        if self.main_device_id:
            for i in range(main_device_combo.count()):
                if main_device_combo.itemData(i) == self.main_device_id:
                    main_device_combo.setCurrentIndex(i)
                    break
                    
        main_device_layout.addWidget(main_device_combo)
        layout.addLayout(main_device_layout)
        
        # 被控设备列表
        layout.addWidget(QLabel("被控设备:"))
        controlled_list = QListWidget()
        
        for device_id, process in self.device_processes.items():
            if device_id != self.main_device_id:
                # 查找设备名称
                device_name = "未知设备"
                for i in range(self.device_combo.count()):
                    if self.device_combo.itemData(i) == device_id:
                        device_name = self.device_combo.itemText(i).split(' (')[0]
                        break
                        
                item = QListWidgetItem(f"{device_name} ({device_id})")
                item.setData(Qt.UserRole, device_id)
                item.setCheckState(Qt.Checked if device_id in self.controlled_devices else Qt.Unchecked)
                controlled_list.addItem(item)
                
        layout.addWidget(controlled_list)
        
        # 群控选项
        options_group = QGroupBox("群控选项")
        options_layout = QVBoxLayout(options_group)
        
        sync_touch_cb = QCheckBox("同步触摸操作")
        sync_touch_cb.setChecked(True)
        
        sync_key_cb = QCheckBox("同步按键操作")
        sync_key_cb.setChecked(True)
        
        sync_text_cb = QCheckBox("同步文本输入")
        sync_text_cb.setChecked(True)
        
        # 添加高级群控模式选项
        advanced_group = QGroupBox("高级功能")
        advanced_layout = QVBoxLayout(advanced_group)
        
        sync_mode_combo = QComboBox()
        sync_mode_combo.addItems(["基础模式", "屏幕内容同步", "命令广播模式"])
        sync_mode_combo.setToolTip("基础模式：通过ADB命令模拟操作\n屏幕内容同步：比较屏幕内容确保一致性\n命令广播模式：向所有设备广播相同命令")
        advanced_layout.addWidget(QLabel("群控模式:"))
        advanced_layout.addWidget(sync_mode_combo)
        
        # 添加命令广播选项
        broadcast_cmd_btn = QPushButton("广播ADB命令")
        broadcast_cmd_btn.clicked.connect(lambda: self.show_broadcast_command_dialog())
        advanced_layout.addWidget(broadcast_cmd_btn)
        
        # 添加截图对比选项
        screenshot_compare_btn = QPushButton("截图对比分析")
        screenshot_compare_btn.clicked.connect(lambda: self.show_screenshot_compare_dialog())
        advanced_layout.addWidget(screenshot_compare_btn)
        
        # 添加屏幕同步选项
        force_sync_btn = QPushButton("强制屏幕同步")
        force_sync_btn.clicked.connect(lambda: self.force_screen_sync())
        advanced_layout.addWidget(force_sync_btn)
        
        options_layout.addWidget(sync_touch_cb)
        options_layout.addWidget(sync_key_cb)
        options_layout.addWidget(sync_text_cb)
        
        # 添加高级选项组
        layout.addWidget(options_group)
        layout.addWidget(advanced_group)
        
        # 说明文字
        info_label = QLabel("同步群控功能通过ADB转发主控设备的操作到所有被控设备。\n"
                           "注意：此功能需要设备分辨率相似才能获得最佳效果。")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # 按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        # 显示对话框
        if dialog.exec_() == QDialog.Accepted:
            # 更新主控设备
            new_main_device = main_device_combo.currentData()
            if new_main_device != self.main_device_id:
                self.main_device_id = new_main_device
                self.sync_control_device_combo.setCurrentText(main_device_combo.currentText())
                self.log(f"已更新主控设备: {self.main_device_id}")
            
            # 更新被控设备列表
            self.controlled_devices = []
            for i in range(controlled_list.count()):
                item = controlled_list.item(i)
                if item.checkState() == Qt.Checked:
                    device_id = item.data(Qt.UserRole)
                    self.controlled_devices.append(device_id)
                    
            self.log(f"已选择 {len(self.controlled_devices)} 个被控设备")
            
            # 更新群控选项
            # (实际实现时需要保存这些设置)
            
            # 重新设置事件监听
            self.setup_event_listeners()
    
    def setup_event_listeners(self):
        """为所有已连接设备自动设置事件监听器"""
        # 输出调试日志
        self.log("开始设置事件监听器...")
        self.log(f"当前设备进程: {list(self.device_processes.keys())}")
        
        # 自动选择主控设备为当前下拉框选择
        if self.device_combo.currentIndex() >= 0:
            self.main_device_id = self.device_combo.currentData()
        else:
            self.main_device_id = None

        self.log(f"选择主控设备: {self.main_device_id}")

        # 被控设备为其余所有已连接设备
        self.controlled_devices = [dev for dev in self.device_processes.keys() if dev != self.main_device_id]
        self.log(f"被控设备列表: {self.controlled_devices}")

        # 停止旧的监听器
        if self.event_monitor:
            self.log("停止旧监听器...")
            self.event_monitor.stop_monitoring()
            self.event_monitor = None

        # 检查主设备进程是否存在并运行
        if not (self.main_device_id and self.main_device_id in self.device_processes and 
                self.device_processes[self.main_device_id].state() == QProcess.Running):
            self.log(f"❌ 主控设备 {self.main_device_id} 未连接，请先连接设备")
            return

        # 检查从设备进程是否运行
        active_slaves = []
        for device_id in self.controlled_devices:
            if device_id in self.device_processes and self.device_processes[device_id].state() == QProcess.Running:
                active_slaves.append(device_id)
        self.controlled_devices = active_slaves
        self.log(f"活动的被控设备: {active_slaves}")

        # 获取活动窗口列表
        active_windows = [w.windowTitle() for w in QApplication.topLevelWidgets() 
                         if hasattr(w, "windowTitle") and w.windowTitle() and w.isVisible()]
        self.log(f"当前活动窗口列表: {active_windows[:10]}")  # 只显示前10个窗口

        # 创建新的监听器
        try:
            self.event_monitor = ScrcpyEventMonitor(
                self, 
                self.controller, 
                self.main_device_id, 
                self.controlled_devices
            )
            # 先让监听器查找设备窗口
            self.event_monitor.find_device_windows()
            # 然后安装全局事件过滤器
            QApplication.instance().installEventFilter(self.event_monitor)
            self.log("✅ 已自动开启事件监控")
            # 强制立即查找并安装事件过滤器
            self.event_monitor.find_and_monitor_windows()
            
            # 检查监控窗口列表
            if hasattr(self.event_monitor, 'monitored_windows') and self.event_monitor.monitored_windows:
                window_count = len(self.event_monitor.monitored_windows)
                window_titles = [w.windowTitle() for w in self.event_monitor.monitored_windows 
                               if hasattr(w, "windowTitle")]
                self.log(f"✅ 成功监控 {window_count} 个窗口: {window_titles}")
            else:
                self.log("⚠️ 未找到任何可监控窗口，请先点击设备窗口")
                
        except Exception as e:
            self.log(f"❌ 设置事件监听器时出错: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def sync_input_to_devices(self, input_type, x, y, action):
        """将输入同步到所有被控设备
        
        Args:
            input_type: 输入类型 (touch, swipe, key)
            x, y: 坐标 (按比例计算)
            action: 具体动作
        """
        if not self.sync_control_enabled or not self.controlled_devices:
            return
            
        # 这里实现事件转发逻辑
        # 例如，将触摸事件转发到每个被控设备
        for device_id in self.controlled_devices:
            # 使用ADB发送输入命令
            # 例如: adb shell input tap x y
            try:
                if input_type == "touch":
                    self.controller.send_touch_event(device_id, x, y, action)
                elif input_type == "key":
                    self.controller.send_key_event(device_id, action)
                elif input_type == "text":
                    self.controller.send_text_input(device_id, action)
            except Exception as e:
                self.log(f"同步操作到设备 {device_id} 失败: {e}")

    # 添加高级群控功能
    def show_broadcast_command_dialog(self):
        """显示广播命令对话框"""
        if not self.sync_control_enabled or not self.controlled_devices:
            QMessageBox.information(self, "群控未启用", "请先启用群控功能并选择被控设备")
            return
            
        dialog = QDialog(self)
        dialog.setWindowTitle("广播ADB命令")
        dialog.setMinimumWidth(500)
        layout = QVBoxLayout(dialog)
        
        layout.addWidget(QLabel("输入要广播到所有被控设备的ADB命令:"))
        
        # 命令输入框
        cmd_input = QLineEdit()
        cmd_input.setPlaceholderText("例如: input tap 500 500")
        layout.addWidget(cmd_input)
        
        # 常用命令快捷选择
        layout.addWidget(QLabel("常用命令:"))
        common_cmds_layout = QHBoxLayout()
        
        tap_btn = QPushButton("点击屏幕")
        tap_btn.clicked.connect(lambda: cmd_input.setText("input tap 500 500"))
        
        swipe_btn = QPushButton("滑动屏幕")
        swipe_btn.clicked.connect(lambda: cmd_input.setText("input swipe 200 500 800 500"))
        
        back_btn = QPushButton("返回键")
        back_btn.clicked.connect(lambda: cmd_input.setText("input keyevent 4"))
        
        home_btn = QPushButton("主页键")
        home_btn.clicked.connect(lambda: cmd_input.setText("input keyevent 3"))
        
        common_cmds_layout.addWidget(tap_btn)
        common_cmds_layout.addWidget(swipe_btn)
        common_cmds_layout.addWidget(back_btn)
        common_cmds_layout.addWidget(home_btn)
        
        layout.addLayout(common_cmds_layout)
        
        # 设备列表
        layout.addWidget(QLabel("选择目标设备:"))
        
        device_list = QListWidget()
        
        # 添加主控设备
        main_item = QListWidgetItem(f"主控: {self.main_device_id}")
        main_item.setData(Qt.UserRole, self.main_device_id)
        main_item.setCheckState(Qt.Checked)
        device_list.addItem(main_item)
        
        # 添加被控设备
        for device_id in self.controlled_devices:
            # 查找设备名称
            device_name = "设备"
            for i in range(self.device_combo.count()):
                if self.device_combo.itemData(i) == device_id:
                    device_name = self.device_combo.itemText(i).split(' (')[0]
                    break
                    
            item = QListWidgetItem(f"{device_name} ({device_id})")
            item.setData(Qt.UserRole, device_id)
            item.setCheckState(Qt.Checked)
            device_list.addItem(item)
            
        layout.addWidget(device_list)
        
        # 日志输出区域
        layout.addWidget(QLabel("执行结果:"))
        
        result_text = QTextEdit()
        result_text.setReadOnly(True)
        result_text.setMaximumHeight(150)
        layout.addWidget(result_text)
        
        # 按钮
        buttons_layout = QHBoxLayout()
        
        execute_btn = QPushButton("执行命令")
        execute_btn.clicked.connect(lambda: self.execute_broadcast_command(
            cmd_input.text(),
            [device_list.item(i).data(Qt.UserRole) 
             for i in range(device_list.count()) 
             if device_list.item(i).checkState() == Qt.Checked],
            result_text
        ))
        
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.reject)
        
        buttons_layout.addWidget(execute_btn)
        buttons_layout.addWidget(close_btn)
        
        layout.addLayout(buttons_layout)
        
        # 显示对话框
        dialog.exec_()
        
    def show_screenshot_compare_dialog(self):
        """显示截图对比分析对话框"""
        if not self.sync_control_enabled or not self.controlled_devices:
            QMessageBox.information(self, "群控未启用", "请先启用群控功能并选择被控设备")
            return
            
        # 首先获取所有设备的截图
        QMessageBox.information(self, "截图对比", "将获取所有设备的截图用于对比分析，这可能需要几秒钟时间。")
        
        # 创建临时目录存储截图
        import tempfile
        temp_dir = tempfile.mkdtemp()
        
        # 获取所有设备的截图
        screenshots = {}
        main_screenshot_path = os.path.join(temp_dir, f"main_{self.main_device_id}.png")
        success, _ = self.controller.capture_screenshot(self.main_device_id, main_screenshot_path)
        
        if not success:
            QMessageBox.warning(self, "截图失败", f"获取主控设备 {self.main_device_id} 的截图失败")
            return
            
        screenshots[self.main_device_id] = main_screenshot_path
        
        # 获取被控设备截图
        for device_id in self.controlled_devices:
            screenshot_path = os.path.join(temp_dir, f"slave_{device_id}.png")
            success, _ = self.controller.capture_screenshot(device_id, screenshot_path)
            if success:
                screenshots[device_id] = screenshot_path
            else:
                self.log(f"获取设备 {device_id} 的截图失败")
                
        if len(screenshots) < 2:
            QMessageBox.warning(self, "截图失败", "获取设备截图失败，无法进行对比")
            return
            
        # 显示对比结果对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("截图对比分析")
        dialog.setMinimumSize(800, 600)
        layout = QVBoxLayout(dialog)
        
        # 添加结果标签
        layout.addWidget(QLabel("截图对比结果:"))
        
        # 结果文本框
        result_text = QTextEdit()
        result_text.setReadOnly(True)
        layout.addWidget(result_text)
        
        # 分析截图差异
        try:
            # 尝试导入PIL库进行图片分析
            from PIL import Image, ImageChops
            
            # 打开主控设备图片
            main_img = Image.open(screenshots[self.main_device_id])
            
            # 逐个与被控设备对比
            for device_id in self.controlled_devices:
                if device_id not in screenshots:
                    continue
                    
                slave_img = Image.open(screenshots[device_id])
                
                # 确保尺寸相同
                if main_img.size != slave_img.size:
                    result_text.append(f"设备 {device_id} 屏幕尺寸与主控不同: {slave_img.size} vs {main_img.size}")
                    continue
                    
                # 计算图像差异
                diff = ImageChops.difference(main_img, slave_img)
                diff_bbox = diff.getbbox()
                
                if diff_bbox:
                    # 有差异
                    x1, y1, x2, y2 = diff_bbox
                    diff_area = (x2 - x1) * (y2 - y1)
                    total_area = main_img.width * main_img.height
                    diff_percent = (diff_area / total_area) * 100
                    
                    result_text.append(f"设备 {device_id} 屏幕内容有 {diff_percent:.2f}% 的差异")
                    result_text.append(f"主要差异区域: ({x1},{y1}) - ({x2},{y2})")
                else:
                    # 无差异
                    result_text.append(f"设备 {device_id} 屏幕内容与主控完全一致")
                    
        except ImportError:
            result_text.append("无法进行图像分析: 缺少PIL库\n请安装Pillow库以使用此功能")
        except Exception as e:
            result_text.append(f"对比截图时发生错误: {str(e)}")
            
        # 按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        # 显示对话框
        dialog.exec_()
        
        # 清理临时文件
        for file_path in screenshots.values():
            try:
                os.remove(file_path)
            except:
                pass
        try:
            os.rmdir(temp_dir)
        except:
            pass
            
    def execute_broadcast_command(self, command, device_ids, result_text):
        """向选中的设备广播执行ADB命令"""
        if not command.strip():
            result_text.append("错误: 命令不能为空")
            return
            
        result_text.clear()
        result_text.append(f"执行命令: {command}")
        result_text.append("---------------------")
        
        success_count = 0
        
        # 逐个设备执行命令
        for device_id in device_ids:
            try:
                # 构建完整命令
                cmd = ["adb", "-s", device_id, "shell", command]
                
                # 执行命令
                kwargs = {}
                if os.name == 'nt':  # Windows
                    kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                    
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    **kwargs
                )
                
                # 获取输出
                stdout, stderr = process.communicate(timeout=5)
                
                if process.returncode == 0:
                    result_text.append(f"设备 {device_id}: 成功")
                    if stdout.strip():
                        result_text.append(f"输出: {stdout.strip()}")
                    success_count += 1
                else:
                    result_text.append(f"设备 {device_id}: 失败 (错误码 {process.returncode})")
                    if stderr.strip():
                        result_text.append(f"错误: {stderr.strip()}")
                        
            except subprocess.TimeoutExpired:
                result_text.append(f"设备 {device_id}: 超时")
            except Exception as e:
                result_text.append(f"设备 {device_id}: 异常 - {str(e)}")
                
        # 显示汇总结果
        result_text.append("---------------------")
        result_text.append(f"命令执行完成: {success_count}/{len(device_ids)} 个设备成功")
        
        # 更新日志
        self.log(f"广播命令 '{command}' 到 {len(device_ids)} 个设备，成功: {success_count}")
        
    def force_screen_sync(self):
        """强制同步所有屏幕内容"""
        if not self.sync_control_enabled or not self.main_device_id or not self.controlled_devices:
            QMessageBox.information(self, "群控未启用", "请先启用群控功能并设置主控和被控设备")
            return
            
        reply = QMessageBox.question(
            self, 
            "强制同步屏幕", 
            "将强制所有被控设备与主控设备的屏幕保持一致。这将执行以下操作:\n\n"
            "1. 在所有设备上按下HOME键返回主屏幕\n"
            "2. 点击相同的应用图标\n"
            "3. 执行相同的操作序列\n\n"
            "是否继续？",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
            
        # 显示进度对话框
        progress_dialog = QDialog(self)
        progress_dialog.setWindowTitle("屏幕同步")
        progress_dialog.setMinimumWidth(400)
        progress_layout = QVBoxLayout(progress_dialog)
        
        progress_label = QLabel("正在同步屏幕...")
        progress_layout.addWidget(progress_label)
        
        # 添加执行步骤
        step_text = QTextEdit()
        step_text.setReadOnly(True)
        step_text.setMaximumHeight(150)
        progress_layout.addWidget(step_text)
        
        # 创建非模态对话框
        progress_dialog.setModal(False)
        progress_dialog.show()
        QApplication.processEvents()
        
        step_text.append("1. 在所有设备上按下HOME键...")
        
        # 首先在所有设备上按下HOME键
        for device_id in [self.main_device_id] + self.controlled_devices:
            self.controller.send_key_event(device_id, 3)  # HOME键
            QApplication.processEvents()
            
        time.sleep(1)
        step_text.append("完成")
        
        # 在主控设备截图，分析主屏幕
        step_text.append("2. 分析主控设备屏幕...")
        QApplication.processEvents()
        
        # 这里是简化实现，实际应用中需要更复杂的图像分析逻辑
        # 使用ADB输入事件模拟点击中心位置
        main_size = self.controller.get_screen_size(self.main_device_id)
        if not main_size:
            step_text.append("获取主控设备屏幕尺寸失败")
            return
            
        center_x = main_size[0] // 2
        center_y = main_size[1] // 2
        
        step_text.append(f"3. 在所有设备屏幕中心({center_x}, {center_y})模拟点击...")
        QApplication.processEvents()
        
        # 在所有设备上点击相同的位置
        for device_id in [self.main_device_id] + self.controlled_devices:
            # 获取设备尺寸
            device_size = self.controller.get_screen_size(device_id)
            if not device_size:
                step_text.append(f"获取设备 {device_id} 屏幕尺寸失败")
                continue
                
            # 计算设备上的相对位置
            x = device_size[0] // 2
            y = device_size[1] // 2
            
            # 点击
            self.controller.send_touch_event(device_id, x, y, "tap")
            QApplication.processEvents()
            time.sleep(0.5)
            
        step_text.append("4. 同步操作完成")
        
        # 添加关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(progress_dialog.accept)
        progress_layout.addWidget(close_btn)
        
        self.log("强制屏幕同步操作已完成")

    def find_device_windows(self):
        print("[调试] 执行 find_device_windows")
        self.parent.log("[调试] 执行 find_device_windows")
        try:
            self.parent.log("🔎 扫描设备窗口中...")
            self.parent._force_update_log()
            
            # 获取所有顶级窗口
            all_windows = QApplication.topLevelWidgets()
            potential_device_windows = []
            
            # 特征匹配：标题中包含"scrcpy"关键字的窗口
            for window in all_windows:
                if not hasattr(window, "windowTitle"):
                    continue
                    
                title = window.windowTitle().strip()
                if not title or title == "Scrcpy GUI - 安卓屏幕控制":
                    continue
                    
                # 记录找到的窗口信息
                window_info = {
                    "window": window,
                    "title": title,
                    "is_scrcpy": "scrcpy" in title.lower(),
                    "has_device_id": self.main_device_id in title or any(slave_id in title for slave_id in self.slave_device_ids),
                    "is_android": "android" in title.lower() or "vivo" in title.lower() or "xiaomi" in title.lower() or "oppo" in title.lower() or "honor" in title.lower() or "huawei" in title.lower()
                }
                
                potential_device_windows.append(window_info)
                
            # 按匹配度给窗口排序
            def score_window(w):
                score = 0
                if w["is_scrcpy"]: score += 10
                if w["has_device_id"]: score += 20
                if w["is_android"]: score += 5
                if " - " in w["title"] and "(" in w["title"] and ")" in w["title"]: score += 3
                return score
                
            potential_device_windows.sort(key=score_window, reverse=True)
            
            # 为高分窗口安装事件过滤器
            added_count = 0
            for window_info in potential_device_windows:
                window = window_info["window"]
                title = window_info["title"]
                score = score_window(window_info)
                
                if score > 0:
                    if window not in self.monitored_windows:
                        self.parent.log(f"✨ 发现可能的设备窗口: {title} (匹配度: {score}/35)")
                        self.parent._force_update_log()
                        
                        # 安装事件过滤器
                        window.installEventFilter(self)
                        self.monitored_windows.append(window)
                        self.window_titles.append(title)
                        added_count += 1
                        
                        # 尝试激活窗口
                        if hasattr(window, "raise_"):
                            window.raise_()
                        if hasattr(window, "activateWindow"):
                            window.activateWindow()
                            
            if added_count > 0:
                self.parent.log(f"✅ 已添加 {added_count} 个设备窗口进行监控")
                self.parent._force_update_log()
            else:
                if not self.monitored_windows:
                    self.parent.log("⚠️ 未检测到任何设备窗口，请确保设备已连接并显示")
                    self.parent._force_update_log()
                
            return added_count > 0
            
        except Exception as e:
            self.parent.log(f"查找设备窗口出错: {str(e)}")
            self.parent._force_update_log()
            print(f"查找设备窗口出错: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
        print(f"[调试] find_device_windows 找到窗口: {[window.windowTitle() for window in QApplication.topLevelWidgets() if hasattr(window, 'windowTitle')]}")
        self.parent.log(f"[调试] find_device_windows 找到窗口: {[window.windowTitle() for window in QApplication.topLevelWidgets() if hasattr(window, 'windowTitle')]}")

def parse_arguments():
    """解析命令行参数"""
    import argparse
    parser = argparse.ArgumentParser(description='Scrcpy GUI - Android设备控制工具')
    parser.add_argument('--app-manager', action='store_true', help='直接打开应用管理器')
    parser.add_argument('--version', action='store_true', help='显示版本信息')
    parser.add_argument('--config', type=str, help='指定配置文件路径')
    return parser.parse_args()

def main():
    # 解析命令行参数
    args = parse_arguments()
    
    # 显示版本信息
    if args.version:
        print("Scrcpy GUI v1.0")
        return

    app = QApplication(sys.argv)
    
    # 设置应用字体
    app_font = QFont("微软雅黑", 9)
    QApplication.setFont(app_font)
    
    # 设置应用程序图标
    icon_path = ""
    for path in [
        "1.ico",                       # 当前目录
        os.path.join(os.getcwd(), "1.ico"),  # 完整路径
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "1.ico"),  # 脚本目录
        os.path.join(os.path.dirname(sys.executable), "1.ico"),  # 可执行文件目录
    ]:
        if os.path.exists(path):
            icon_path = path
            break
            
    if icon_path:
        try:
            app_icon = QIcon(icon_path)
            if not app_icon.isNull():
                app.setWindowIcon(app_icon)
                print(f"已设置应用程序图标: {icon_path}")
        except Exception as e:
            print(f"应用程序图标设置失败: {e}")
    
    # 创建并显示主窗口
    main_window = ScrcpyUI()
    main_window.show()
    
    # 如果指定了打开应用管理器，则打开它
    if args.app_manager:
        # 使用QTimer.singleShot确保主窗口已完全加载
        QTimer.singleShot(100, main_window.show_app_manager)
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 