#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import subprocess
import time
import math
from functools import partial
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
        
        # 计算界面缩放，先设置主题再应用尺寸缩放
        self.ui_scale = self.compute_ui_scale_v2()
        self.apply_dark_theme()
        self.apply_scale_styles()
        
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
            
            # 清理所有控制栏
            if hasattr(self, 'control_bars'):
                for device_id, control_bar in list(self.control_bars.items()):
                    try:
                        control_bar.deleteLater()
                        print(f"已删除设备 {device_id} 的控制栏")
                    except Exception as e:
                        print(f"删除控制栏时出错: {e}")
                self.control_bars.clear()
            
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
            
            # 仅在追加后滚动到底，避免频繁 repaint 卡顿
            scrollbar = self.log_text.verticalScrollBar()
            if scrollbar:
                scrollbar.setValue(scrollbar.maximum())
            
            # 打印到控制台，增加调试信息
            print(f"[{timestamp}] {message}")
        except Exception as e:
            print(f"添加日志时出错: {e}, 消息: {message}")

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

    def compute_ui_scale(self):
        """根据可用屏幕尺寸计算界面缩放因子"""
        try:
            screen = QApplication.primaryScreen()
            avail = screen.availableGeometry() if screen else None
            if not avail:
                return 0.9
            w, h = avail.width(), avail.height()
            base_w, base_h = 1920, 1080
            scale = min(w / base_w, h / base_h)
            # 限制缩放范围，让组件更紧凑一些
            return max(0.75, min(scale, 1.0))
        except Exception:
            return 0.9

    def compute_ui_scale_v2(self):
        """Compute a compact UI scale based on resolution and DPI."""
        try:
            screen = QApplication.primaryScreen()
            avail = screen.availableGeometry() if screen else None
            if not avail:
                return 0.8
            w, h = avail.width(), avail.height()
            base_w, base_h = 1920, 1080
            res_ratio = min(w / base_w, h / base_h)
            base_scale = 0.8
            res_factor = 1.0
            if res_ratio > 1.0:
                res_factor = 1.0 / (res_ratio ** 0.35)
            dpi = screen.logicalDotsPerInch() if screen else 96.0
            if not dpi:
                dpi = 96.0
            self.ui_dpi = dpi
            dpi_factor = min(1.0, 96.0 / dpi)
            scale = base_scale * res_factor * dpi_factor
            return max(0.6, min(scale, 0.9))
        except Exception:
            return 0.8

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
            
            /* 为导航按钮添加样式 */
            QPushButton#home_btn, QPushButton#back_btn, QPushButton#menu_btn {
                background-color: #673AB7;
                color: white;
                font-weight: bold;
                padding: 8px 15px;
                min-width: 100px;
                border-radius: 4px;
                margin: 2px;
            }
            QPushButton#home_btn:hover, QPushButton#back_btn:hover, QPushButton#menu_btn:hover {
                background-color: #5E35B1;
            }
            QPushButton#home_btn:pressed, QPushButton#back_btn:pressed, QPushButton#menu_btn:pressed {
                background-color: #512DA8;
            }
        """)
    
    def apply_scale_styles(self):
        """根据计算的缩放因子微调字体和间距，让组件随屏幕缩放"""
        scale = getattr(self, 'ui_scale', 1.0)
        def px(v):
            return f"{max(1, int(round(v * scale)))}px"
        font_pt = max(7, int(round(9 * scale)))
        small_font_pt = max(7, int(round(8 * scale)))
        dpi = getattr(self, 'ui_dpi', 96.0)
        use_px_font = dpi <= 110
        if use_px_font:
            font_px = max(10, int(round(font_pt * 1.3)))
            small_font_px = max(9, int(round(small_font_pt * 1.3)))
            widget_font_rule = f"font-size: {font_px}px;"
            text_font_rule = f"font-size: {small_font_px}px;"
        else:
            widget_font_rule = f"font-size: {font_pt}pt;"
            text_font_rule = f"font-size: {small_font_pt}pt;"
        style = f"""
        QWidget {{
            {widget_font_rule}
        }}
        QPushButton {{
            padding: {px(2)} {px(7)};
            min-height: {px(20)};
        }}
        QLineEdit, QComboBox {{
            padding: {px(2)} {px(6)};
            min-height: {px(22)};
        }}
        QGroupBox {{
            margin-top: {px(5)};
            padding-top: {px(8)};
            border-radius: {px(4)};
        }}
        QGroupBox::title {{
            left: {px(8)};
            padding: 0 {px(4)};
            font-size: {font_pt}pt;
        }}
        QComboBox::drop-down {{
            width: {px(16)};
        }}
        QCheckBox {{
            spacing: {px(4)};
        }}
        QCheckBox::indicator {{
            width: {px(14)};
            height: {px(14)};
        }}
        QPushButton#home_btn, QPushButton#back_btn, QPushButton#menu_btn {{
            padding: {px(2)} {px(6)};
            min-width: {px(72)};
            margin: {px(1)};
        }}
        QTextEdit {{
            {text_font_rule}
        }}
        """
        self.setStyleSheet(self.styleSheet() + "\n" + style)
    
    def apply_dark_theme(self):
        """应用现代浅色主题（覆盖旧样式定义）"""
        palette = QPalette()
        background_color = QColor(244, 243, 240)
        panel_color = QColor(255, 255, 255)
        text_color = QColor(28, 30, 33)
        accent = QColor(42, 122, 108)

        palette.setColor(QPalette.Window, background_color)
        palette.setColor(QPalette.WindowText, text_color)
        palette.setColor(QPalette.Base, panel_color)
        palette.setColor(QPalette.AlternateBase, QColor(250, 249, 247))
        palette.setColor(QPalette.ToolTipBase, panel_color)
        palette.setColor(QPalette.ToolTipText, text_color)
        palette.setColor(QPalette.Text, text_color)
        palette.setColor(QPalette.Disabled, QPalette.Text, QColor(150, 150, 150))
        palette.setColor(QPalette.Button, panel_color)
        palette.setColor(QPalette.ButtonText, text_color)
        palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(150, 150, 150))
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, accent)
        palette.setColor(QPalette.Highlight, accent)
        palette.setColor(QPalette.HighlightedText, Qt.white)
        self.setPalette(palette)

        self.setStyleSheet("""
            QGroupBox {
                border: 1px solid #e2e0dc;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 14px;
                font-weight: 600;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 5px;
                color: #2a7a6c;
            }
            QPushButton {
                background-color: #2a7a6c;
                color: #ffffff;
                border: 1px solid #1f5c52;
                border-radius: 5px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #246a5e; }
            QPushButton:pressed { background-color: #1f5c52; }
            QPushButton:disabled {
                background-color: #d3d1cc;
                color: #8d8a84;
                border: 1px solid #c9c6c0;
            }
            QPushButton#usb_btn, QPushButton#wifi_btn {
                background-color: #3b8a76;
                border-color: #2f6e60;
            }
            QPushButton#usb_btn:hover, QPushButton#wifi_btn:hover { background-color: #327665; }
            QPushButton#usb_btn:pressed, QPushButton#wifi_btn:pressed { background-color: #2a6356; }
            QPushButton#connect_all_btn {
                background-color: #caa15a;
                border-color: #b58b45;
                color: #2f2a24;
            }
            QPushButton#connect_all_btn:hover { background-color: #bb9150; }
            QPushButton#connect_all_btn:pressed { background-color: #a77f44; }
            QPushButton#stop_btn {
                background-color: #c85b52;
                border-color: #b24a43;
            }
            QPushButton#stop_btn:hover { background-color: #b95149; }
            QPushButton#stop_btn:pressed { background-color: #a64740; }
            QPushButton#screenshot_btn { background-color: #2a7a6c; }
            QPushButton#screenshot_btn:hover { background-color: #246a5e; }
            QPushButton#screenshot_btn:pressed { background-color: #1f5c52; }
            QPushButton#clear_log_btn {
                background-color: #7b7770;
                border-color: #67635c;
            }
            QPushButton#clear_log_btn:hover { background-color: #6e6a64; }
            QPushButton#clear_log_btn:pressed { background-color: #5f5b56; }
            QLineEdit, QComboBox {
                border: 1px solid #e2e0dc;
                border-radius: 5px;
                background-color: #ffffff;
                color: #1c1e21;
                selection-background-color: #dcebe7;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 20px;
                border-left: 1px solid #e2e0dc;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #e2e0dc;
                background-color: #ffffff;
                selection-background-color: #dcebe7;
                selection-color: #1c1e21;
            }
            QCheckBox { color: #1c1e21; }
            QCheckBox::indicator {
                border: 1px solid #d7d5d1;
                border-radius: 4px;
                background-color: #ffffff;
            }
            QCheckBox::indicator:checked {
                background-color: #2a7a6c;
                border-color: #2a7a6c;
            }
            QCheckBox::indicator:hover { border-color: #2a7a6c; }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                border: 1px solid #2a7a6c;
                outline: none;
            }
            QTextEdit {
                border: 1px solid #e0ded9;
                border-radius: 5px;
                background-color: #fbfaf8;
                color: #2a2a2a;
            }
            QListWidget {
                border: 1px solid #e0ded9;
                border-radius: 5px;
            }
            QListWidget::item:selected {
                background-color: #dcebe7;
                color: #1c1e21;
            }
            QMenuBar {
                background-color: #f1efec;
                border-bottom: 1px solid #e2e0dc;
            }
            QMenuBar::item { padding: 4px 10px; }
            QMenuBar::item:selected { background: #e6e3de; }
            QMenu {
                border: 1px solid #e2e0dc;
                background-color: #ffffff;
            }
            QMenu::item:selected { background-color: #e6e3de; }
            QFrame#line {
                background-color: #e2e0dc;
                max-height: 1px;
            }
            QLabel#title {
                color: #2a7a6c;
                font-size: 15px;
                font-weight: 700;
            }
            QStatusBar {
                background-color: #f1efec;
                border-top: 1px solid #e2e0dc;
            }
            QPushButton#about_btn {
                background-color: #4d6b9a;
                border-color: #3d557a;
            }
            QPushButton#about_btn:hover { background-color: #425c88; }
            QPushButton#about_btn:pressed { background-color: #374e73; }
            QScrollBar:vertical {
                border: none;
                background: #f0eeea;
                width: 9px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #c7c2b8;
                min-height: 18px;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            /* 导航按钮 */
            QPushButton#home_btn, QPushButton#back_btn, QPushButton#menu_btn {
                background-color: #4d6b9a;
                color: #ffffff;
                font-weight: 600;
                border-radius: 5px;
                border: 1px solid #3d557a;
            }
            QPushButton#home_btn:hover, QPushButton#back_btn:hover, QPushButton#menu_btn:hover {
                background-color: #425c88;
            }
            QPushButton#home_btn:pressed, QPushButton#back_btn:pressed, QPushButton#menu_btn:pressed {
                background-color: #374e73;
            }
        """)
        
    def find_adb_path(self):
        """查找adb路径，优先使用程序目录中的adb"""
        try:
            def dedup_repeated_dir(path):
                """Collapse duplicated parent folders like foo/foo/file.ext"""
                norm = os.path.normpath(path)
                if os.path.exists(norm):
                    return norm
                parts = norm.split(os.sep)
                if len(parts) >= 4 and parts[-2].lower() == parts[-3].lower():
                    parts.pop(-3)
                    collapsed = os.sep.join(parts)
                    if os.path.exists(collapsed):
                        return collapsed
                return norm

            def find_local_adb(base_dir):
                """Search for adb under base_dir (depth limited)"""
                if not base_dir or not os.path.isdir(base_dir):
                    return None
                candidates = ("adb.exe", "adb")
                # Check root first
                for name in candidates:
                    root_candidate = os.path.join(base_dir, name)
                    if os.path.isfile(root_candidate):
                        return dedup_repeated_dir(root_candidate)
                # Walk shallowly to avoid huge trees
                max_depth = 2
                for root, dirs, files in os.walk(base_dir):
                    depth = os.path.relpath(root, base_dir).count(os.sep)
                    if depth > max_depth:
                        dirs[:] = []
                        continue
                    dirs[:] = [d for d in dirs if d not in (".git", ".venv", "__pycache__")]
                    for name in candidates:
                        candidate = os.path.join(root, name)
                        if os.path.isfile(candidate):
                            return dedup_repeated_dir(candidate)
                return None

            # PyInstaller packaged env: search inside bundle directory
            if getattr(sys, 'frozen', False):
                base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
                bundled_adb = find_local_adb(base_path)
                if bundled_adb:
                    self.log(f"使用打包的adb: {bundled_adb}")
                    return bundled_adb
            
            # 首选运行目录，其次脚本目录（不固定文件夹名）
            search_roots = []
            cwd = os.getcwd()
            if os.path.isdir(cwd):
                search_roots.append(cwd)
            script_dir = os.path.dirname(os.path.abspath(__file__))
            if os.path.isdir(script_dir) and script_dir not in search_roots:
                search_roots.append(script_dir)
            exe_dir = os.path.dirname(sys.executable) if sys.executable else ""
            if exe_dir and os.path.isdir(exe_dir) and exe_dir not in search_roots:
                search_roots.append(exe_dir)
            exe_dir = os.path.dirname(sys.executable) if sys.executable else ""
            if exe_dir and os.path.isdir(exe_dir) and exe_dir not in search_roots:
                search_roots.append(exe_dir)

            for root in search_roots:
                local_adb = find_local_adb(root)
                if local_adb:
                    self.log(f"使用本地adb: {local_adb}")
                    return local_adb
                
            # 环境变量 PATH
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creationflags = subprocess.CREATE_NO_WINDOW
                result = subprocess.run(
                    ['where', 'adb'],
                    capture_output=True,
                    text=True,
                    check=False,
                    startupinfo=startupinfo,
                    creationflags=creationflags
                )

                if result.returncode == 0 and result.stdout:
                    for line in result.stdout.splitlines():
                        adb_candidate = line.strip()
                        if adb_candidate:
                            return adb_candidate
            else:
                # 在Linux和macOS下查找
                result = subprocess.run(['which', 'adb'], 
                                      capture_output=True, 
                                      text=True, 
                                      check=False)
                
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            
            # 常见路径兜底
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
            
            # 仍然没有找到时返回默认命令名
            return 'adb'
        except Exception as e:
            self.log(f"查找adb路径出错: {e}")
            return 'adb'
        
    def find_scrcpy_path(self):
        """查找scrcpy路径"""
        try:
            def dedup_repeated_dir(path):
                """Collapse duplicated parent folders like foo/foo/file.ext"""
                norm = os.path.normpath(path)
                if os.path.exists(norm):
                    return norm
                parts = norm.split(os.sep)
                if len(parts) >= 4 and parts[-2].lower() == parts[-3].lower():
                    parts.pop(-3)
                    collapsed = os.sep.join(parts)
                    if os.path.exists(collapsed):
                        return collapsed
                return norm

            def find_local_scrcpy(base_dir):
                """Search for scrcpy under base_dir (depth limited)"""
                if not base_dir or not os.path.isdir(base_dir):
                    return None
                candidates = ("scrcpy.exe", "scrcpy")
                # Check root first
                for name in candidates:
                    root_candidate = os.path.join(base_dir, name)
                    if os.path.isfile(root_candidate):
                        return dedup_repeated_dir(root_candidate)
                # Walk shallowly to avoid huge trees
                max_depth = 2
                for root, dirs, files in os.walk(base_dir):
                    depth = os.path.relpath(root, base_dir).count(os.sep)
                    if depth > max_depth:
                        dirs[:] = []
                        continue
                    dirs[:] = [d for d in dirs if d not in (".git", ".venv", "__pycache__")]
                    for name in candidates:
                        candidate = os.path.join(root, name)
                        if os.path.isfile(candidate):
                            return dedup_repeated_dir(candidate)
                return None

            def resolve_scrcpy_with_server(scrcpy_path):
                """Prefer scrcpy that has scrcpy-server in the same directory."""
                if not scrcpy_path:
                    return None
                server_dir = os.path.dirname(scrcpy_path)
                for name in ("scrcpy-server", "scrcpy-server.jar"):
                    server_path = os.path.join(server_dir, name)
                    if os.path.isfile(server_path):
                        os.environ["SCRCPY_SERVER_PATH"] = server_path
                        return scrcpy_path
                return None

            def find_scrcpy_in_path():
                """Yield scrcpy candidates found in PATH, in order."""
                path_env = os.environ.get("PATH", "")
                if not path_env:
                    return []
                candidates = []
                exe_name = "scrcpy.exe" if os.name == "nt" else "scrcpy"
                for entry in path_env.split(os.pathsep):
                    entry = entry.strip('"')
                    if not entry:
                        continue
                    candidate = os.path.join(entry, exe_name)
                    if os.path.isfile(candidate):
                        candidates.append(candidate)
                return candidates

            # 检查是否是PyInstaller打包环境
            if getattr(sys, 'frozen', False):
                # 在PyInstaller环境中，使用_MEIPASS查找打包的资源目录
                base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
                bundled_scrcpy = find_local_scrcpy(base_path)
                if bundled_scrcpy:
                    resolved = resolve_scrcpy_with_server(bundled_scrcpy)
                    if resolved:
                        self.log(f"使用打包的scrcpy: {resolved}")
                        return resolved
            
            # 首选运行目录，其次脚本目录（不固定文件夹名）
            search_roots = []
            cwd = os.getcwd()
            if os.path.isdir(cwd):
                search_roots.append(cwd)
            script_dir = os.path.dirname(os.path.abspath(__file__))
            if os.path.isdir(script_dir) and script_dir not in search_roots:
                search_roots.append(script_dir)

            for root in search_roots:
                local_scrcpy = find_local_scrcpy(root)
                if local_scrcpy:
                    resolved = resolve_scrcpy_with_server(local_scrcpy)
                    if resolved:
                        self.log(f"使用本地scrcpy: {resolved}")
                        return resolved
                
            # 如果本地没有，才尝试通过环境变量PATH查找
            if os.name == 'nt':
                path_candidates = find_scrcpy_in_path()
                if path_candidates:
                    fallback = None
                    for scrcpy_candidate in path_candidates:
                        if not fallback:
                            fallback = scrcpy_candidate
                        resolved = resolve_scrcpy_with_server(scrcpy_candidate)
                        if resolved:
                            return resolved
                    if fallback:
                        self.log(f"警告: {fallback} 同目录下未找到 scrcpy-server，仍将使用该路径")
                        return fallback

                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creationflags = subprocess.CREATE_NO_WINDOW
                # 在Windows下尝试查找
                result = subprocess.run(
                    ['where', 'scrcpy'], 
                    capture_output=True, 
                    text=True, 
                    check=False,
                    startupinfo=startupinfo,
                    creationflags=creationflags
                )
                
                if result.returncode == 0 and result.stdout:
                    fallback = None
                    for line in result.stdout.splitlines():
                        scrcpy_candidate = line.strip()
                        if scrcpy_candidate:
                            if not fallback:
                                fallback = scrcpy_candidate
                            resolved = resolve_scrcpy_with_server(scrcpy_candidate)
                            if resolved:
                                return resolved
                    if fallback:
                        self.log(f"警告: {fallback} 同目录下未找到 scrcpy-server，仍将使用该路径")
                        return fallback
            else:
                # 在Linux和macOS下查找
                path_candidates = find_scrcpy_in_path()
                if path_candidates:
                    fallback = None
                    for scrcpy_candidate in path_candidates:
                        if not fallback:
                            fallback = scrcpy_candidate
                        resolved = resolve_scrcpy_with_server(scrcpy_candidate)
                        if resolved:
                            return resolved
                    if fallback:
                        self.log(f"警告: {fallback} 同目录下未找到 scrcpy-server，仍将使用该路径")
                        return fallback

                result = subprocess.run(['which', 'scrcpy'], 
                                       capture_output=True, 
                                       text=True, 
                                       check=False)
                
                if result.returncode == 0 and result.stdout.strip():
                    candidate = result.stdout.strip()
                    resolved = resolve_scrcpy_with_server(candidate)
                    if resolved:
                        return resolved
                    return candidate
            
            # 如果没有找到，尝试一些常见的路径
            common_paths = [
                os.path.join(os.environ.get('LOCALAPPDATA', ''), 'scrcpy', 'scrcpy.exe'),
                os.path.join(os.environ.get('ProgramFiles', ''), 'scrcpy', 'scrcpy.exe'),
                os.path.join(os.environ.get('ProgramFiles(x86)', ''), 'scrcpy', 'scrcpy.exe'),
                '/usr/bin/scrcpy',
                '/usr/local/bin/scrcpy'
            ]
        
            fallback = None
            for path in common_paths:
                if os.path.isfile(path):
                    if not fallback:
                        fallback = path
                    resolved = resolve_scrcpy_with_server(path)
                    if resolved:
                        return resolved
            if fallback:
                self.log(f"警告: {fallback} 同目录下未找到 scrcpy-server，仍将使用该路径")
                return fallback
            
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
        # 根据屏幕可用尺寸智能自适应，略微再降低高度
        screen = QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else None
        base_w, base_h = 760, 540
        if avail:
            w = avail.width()
            h = avail.height()
            # 大屏减小比例，小屏保持适中
            frac_w = 0.46 if w < 1920 else 0.38
            frac_h = 0.48 if h < 1080 else 0.40
            base_w = max(640, min(int(w * frac_w), 900))
            base_h = max(480, min(int(h * frac_h), 680))
        self.resize(base_w, base_h)
        self.setMinimumSize(620, 460)
        
        # 创建菜单栏
        self.create_menus()
        
        # 创建中央部件和主布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        scale = getattr(self, 'ui_scale', 1.0)
        margin = max(8, int(round(12 * scale)))
        spacing = max(6, int(round(9 * scale)))
        def scaled(value, min_value):
            return max(min_value, int(round(value * scale)))
        layout_margin = max(6, int(round(8 * scale)))
        layout_spacing = max(4, int(round(6 * scale)))
        def compact_layout(layout, margin_value=None, spacing_value=None):
            m = layout_margin if margin_value is None else margin_value
            s = layout_spacing if spacing_value is None else spacing_value
            layout.setContentsMargins(m, m, m, m)
            layout.setSpacing(s)
        main_layout.setContentsMargins(margin, margin, margin, margin)
        main_layout.setSpacing(spacing)
        
        # 创建设备管理区域
        device_group = QGroupBox("设备连接")
        device_layout = QHBoxLayout(device_group)
        compact_layout(device_layout)
        
        # 设备选择区域
        device_label = QLabel("设备:")
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(scaled(220, 160))
        
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
        compact_layout(connection_layout, margin_value=0, spacing_value=layout_spacing)
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
        compact_layout(mirror_layout)
        
        # 比特率
        bitrate_label = QLabel("比特率:")
        self.bitrate_input = QLineEdit("6")
        self.bitrate_input.setMaximumWidth(scaled(72, 56))
        bitrate_unit = QLabel("Mbps")
        
        # 最大尺寸
        maxsize_label = QLabel("最大尺寸:")
        self.maxsize_input = QLineEdit("1080")
        self.maxsize_input.setMaximumWidth(scaled(72, 56))
        
        # 录制格式
        format_label = QLabel("录制格式:")
        self.format_combo = QComboBox()
        self.format_combo.addItems(["mp4", "mkv"])
        self.format_combo.setMaximumWidth(scaled(88, 70))
        
        # 限制方向
        rotation_label = QLabel("限制方向:")
        self.rotation_combo = QComboBox()
        self.rotation_combo.addItems(["不限制", "横屏", "竖屏"])
        self.rotation_combo.setMaximumWidth(scaled(88, 70))
        
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
        compact_layout(options_layout)
        
        self.record_cb = QCheckBox("录制屏幕")
        self.fullscreen_cb = QCheckBox("全屏显示")
        self.always_top_cb = QCheckBox("窗口置顶")
        self.show_touches_cb = QCheckBox("显示触摸")
        self.no_control_cb = QCheckBox("无交互")
        self.disable_clipboard_cb = QCheckBox("禁用剪贴板")
        
        # 添加同步群控选项
        self.sync_control_cb = QCheckBox("同步群控（维护中）")
        self.sync_control_cb.setToolTip("该功能暂未完成，当前版本默认禁用")
        self.sync_control_cb.setEnabled(False)
        self.sync_control_cb.stateChanged.connect(self.toggle_sync_control)
        
        self.sync_control_device_combo = QComboBox()
        self.sync_control_device_combo.setEnabled(False)
        self.sync_control_device_combo.setToolTip("选择主控设备（功能维护中）")
        self.sync_control_device_combo.setMinimumWidth(scaled(140, 120))
        
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
        
        # 添加同步群控选项到新的一行
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
        
        # 添加各个区域到主布局 - 不再包含导航按钮组
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
        
        # 默认关闭音频，避免设备不支持音频采集时崩溃
        cmd.append('--no-audio')
        
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
            
        except Exception as e:
            self.log(f"启动 scrcpy 失败: {str(e)}")
            if device_id in self.device_processes:
                del self.device_processes[device_id]

    def create_process_finished_handler(self, device_id):
        """创建进程结束处理器"""
        def handler(exit_code, exit_status):
            # 进程结束处理
            self.log(f"设备 {device_id} 的 scrcpy 进程已结束 (代码: {exit_code})")
            
            # 从进程字典中移除
            if device_id in self.device_processes:
                del self.device_processes[device_id]
                
        return handler
        
    def stop_scrcpy(self):
        """停止scrcpy进程"""
        if self.device_combo.currentIndex() < 0:
            # 如果没有选择设备，直接停止所有进程
            self.stop_all_scrcpy()
            return
            
        device_id = self.device_combo.currentData()
        
        if device_id in self.device_processes:
            process = self.device_processes[device_id]
            
            if process.state() == QProcess.Running:
                # 要求进程终止
                self.log(f"正在停止设备 {device_id} 的 scrcpy 进程...")
                
                # 终止进程
                process.terminate()
                
                # 给进程一点时间自行终止
                if not process.waitForFinished(2000):
                    # 如果进程没有自行终止，则强制终止
                    process.kill()
                
                # 从字典中移除
                del self.device_processes[device_id]
                
                self.log(f"已停止设备 {device_id} 的 scrcpy 进程")
            else:
                self.log(f"设备 {device_id} 没有运行中的 scrcpy 进程")
        else:
            self.log(f"设备 {device_id} 没有运行中的 scrcpy 进程")
            
    
    def stop_all_scrcpy(self):
        """停止所有scrcpy进程"""
        if not self.device_processes:
            self.log("没有运行中的 scrcpy 进程")
            return
        self._terminate_all_processes()
        self.log("已停止所有scrcpy进程")

    def _terminate_all_processes(self, timeout_ms=2000):
        """集中终止当前已知的所有QProcess实例"""
        if hasattr(self, 'device_processes'):
            for device_id, process in list(self.device_processes.items()):
                try:
                    if process and process.state() == QProcess.Running:
                        print(f"正在终止设备 {device_id} 的进程...")
                        try:
                            process.disconnect()
                        except Exception:
                            pass
                        process.kill()
                        process.waitForFinished(timeout_ms)
                        print(f"已终止设备 {device_id} 的进程")
                except Exception as e:
                    print(f"终止设备 {device_id} 进程时出错: {e}")
            self.device_processes.clear()

        if hasattr(self, 'process_tracking'):
            for i, proc in enumerate(self.process_tracking):
                try:
                    if proc and proc.state() == QProcess.Running:
                        proc.disconnect()
                        proc.kill()
                        proc.waitForFinished(timeout_ms)
                        print(f"已终止跟踪进程#{i}")
                except Exception as e:
                    print(f"终止跟踪进程 #{i} 时出错: {e}")
            self.process_tracking.clear()

        if hasattr(self, 'process') and self.process and self.process.state() == QProcess.Running:
            try:
                self.process.disconnect()
                self.process.kill()
                self.process.waitForFinished(timeout_ms)
            except Exception as e:
                print(f"终止主进程时出错: {e}")

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
        
    # 添加设备导航按钮的事件处理方法
    def send_home_key(self):
        """发送主页键"""
        pass
    
    def send_back_key(self):
        """发送返回键"""
        pass
    
    def send_menu_key(self):
        """发送菜单键"""
        pass

    def find_device_windows(self):
        """占位函数，已停用"""
        pass

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
        app_manager = AppManagerDialog(self, self.controller) # 原始调用不传递device_id
        app_manager.exec_()

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
        
        # 为每个设备启动一个scrcpy进程
        for device_id, model in devices:
            # 检查设备是否已经连接
            if device_id in self.device_processes and self.device_processes[device_id].state() == QProcess.Running:
                self.log(f"设备 {model} ({device_id}) 已经在运行")
                continue
                
            # 构建命令参数
            cmd = [self.scrcpy_path]
            cmd.extend(['-s', device_id])
            
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
            
            # 默认关闭音频，避免不支持音频采集时的崩溃
            cmd.append('--no-audio')

            # 添加窗口位置参数，避免所有窗口重叠
            cmd.extend(['--window-x', str(100 + count * 50)])
            cmd.extend(['--window-y', str(100 + count * 50)])
            
            try:
                # 创建进程
                process = QProcess()
                
                # 确保进程不被过早销毁
                self.process_tracking.append(process)
                
                # 连接信号
                process.readyReadStandardOutput.connect(lambda proc=process, dev=device_id: self.handle_process_output(proc, dev))
                process.readyReadStandardError.connect(lambda proc=process, dev=device_id: self.handle_process_error(proc, dev))
                
                # 使用新方式连接finished信号
                process.finished.connect(self.create_process_finished_handler(device_id))
                
                # 保存进程
                self.device_processes[device_id] = process
                
                # 启动进程
                process.start(cmd[0], cmd[1:])
                self.log(f"已启动设备 {model} ({device_id}) 的 scrcpy 进程")
                count += 1
                
                # 使用相同的递归尝试方法创建控制栏
                delay_times = [2000, 3500, 5000, 7000, 10000]  # 多个时间点尝试
                
                def attempt_create_control_bar(d_id, w_title, attempt_index=0):
                    """递归尝试创建控制栏，直到成功或达到最大尝试次数"""
                    if attempt_index >= len(delay_times):
                        self.log(f"⚠️ 设备 {d_id} 控制栏创建尝试已达最大次数")
                        return
                        
                    success = self.create_control_bar(d_id, w_title)
                    if not success and attempt_index + 1 < len(delay_times):
                        # 如果创建失败但还有尝试次数，则延迟后再次尝试
                        next_delay = delay_times[attempt_index + 1] - delay_times[attempt_index]
                        self.log(f"设备 {d_id}: 将在 {next_delay/1000} 秒后再次尝试创建控制栏")
                        QTimer.singleShot(next_delay, partial(attempt_create_control_bar, d_id, w_title, attempt_index + 1))
                
                # 启动第一次尝试
                QTimer.singleShot(delay_times[0], partial(attempt_create_control_bar, device_id, window_title, 0))
                
                # 每个设备启动后稍微等待一下，避免系统资源争用
                if count < len(devices):
                    time.sleep(1.0)
                
            except Exception as e:
                self.log(f"启动设备 {model} ({device_id}) 失败: {str(e)}")
                if device_id in self.device_processes:
                    del self.device_processes[device_id]
                    
        if count > 0:
            self.log(f"成功连接 {count} 个设备")

    # 添加群控相关基本方法
    def toggle_sync_control(self, state):
        """开启或关闭同步群控功能"""
        is_enabled = (state == Qt.Checked)
        self.sync_control_device_combo.setEnabled(is_enabled)
        self.sync_control_settings_btn.setEnabled(is_enabled)
        
        if is_enabled:
            self.log("已开启同步群控功能 (注意: 该功能目前尚未完全实现)")
        else:
            self.log("已关闭同步群控功能")
    
    def show_sync_control_settings(self):
        """显示群控设置对话框"""
        QMessageBox.information(self, "群控功能", "同步群控功能目前处于维护中，将在后续版本中恢复完整功能。")
        self.log("群控功能目前尚未完全实现，敬请期待后续版本")

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

    # 高DPI自适应（在创建 QApplication 前设置）
    try:
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        QApplication.setAttribute(Qt.AA_Use96Dpi, True)
    except Exception:
        pass

    app = QApplication(sys.argv)
    
    # 设置应用字体
    app_font = QFont("微软雅黑")
    try:
        screen = app.primaryScreen()
        dpi = screen.logicalDotsPerInch() if screen else 96.0
        if dpi <= 110:
            app_font.setPixelSize(11)
        else:
            app_font.setPointSize(8)
        app_font.setHintingPreference(QFont.PreferFullHinting)
    except Exception:
        app_font.setPointSize(8)
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
