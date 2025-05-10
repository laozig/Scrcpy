#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QWidget, 
    QPushButton, QLabel, QListWidget, QListWidgetItem, QComboBox,
    QMessageBox, QGridLayout, QGroupBox, QLineEdit, QProgressBar,
    QSplitter, QTabWidget, QTextEdit, QCheckBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import QIcon, QPixmap, QFont

"""
应用管理器，用于管理和操作Android设备上的应用程序。

功能：
1. 获取并显示已安装的应用列表
2. 启动、停止和卸载应用
3. 刷新设备列表和应用列表
"""

class AppListThread(QThread):
    """加载应用列表的后台线程"""
    app_loaded = pyqtSignal(list)
    loading_progress = pyqtSignal(int, int)  # 当前数量、总数量
    app_icon_loaded = pyqtSignal(str, bytes)  # 包名, 图标字节数据
    
    def __init__(self, controller, device_id, show_system=False, load_icons=True):
        super().__init__()
        self.controller = controller
        self.device_id = device_id
        self.show_system = show_system
        self.load_icons = load_icons
        
    def run(self):
        # 检查设备ID是否有效
        if not self.device_id:
            print("未找到设备ID，无法获取应用列表")
            self.app_loaded.emit([])
            return
            
        # 构建获取包列表的命令
        if self.show_system:
            cmd = "shell pm list packages"  # 获取所有应用，包括系统应用
        else:
            cmd = "shell pm list packages -3"  # 只获取第三方应用

        print(f"执行命令: adb -s {self.device_id} {cmd}")
        
        # 执行命令并获取结果
        result = self.controller.execute_adb_command(cmd, self.device_id)
        if not result[0] or not result[1]:
            print(f"获取应用列表失败: {result[1] if result[1] else '未知错误'}")
            self.app_loaded.emit([])
            return
            
        # 解析应用列表
        package_list = []
        lines = result[1].strip().split('\n')
        total_apps = len(lines)
        
        for i, line in enumerate(lines):
            self.loading_progress.emit(i+1, total_apps)
            
            # 格式: package:com.example.app
            if line.startswith('package:'):
                package_name = line[8:].strip()
                
                # 默认使用包名最后一部分作为初始显示名称
                display_name = package_name.split('.')[-1].capitalize()
                
                # 获取应用真实名称
                app_name = self.get_app_name(package_name)
                if app_name and app_name != display_name:
                    display_name = app_name
                
                package_list.append((display_name, package_name))
        
        # 按名称排序
        package_list.sort()
        print(f"找到应用数量: {len(package_list)}")
        self.app_loaded.emit(package_list)
        
        # 如果需要加载图标，在后台加载
        if self.load_icons and len(package_list) > 0:
            # 仅为前30个应用加载图标以提高性能
            for i, (_, package_name) in enumerate(package_list[:30]):
                # 使用默认图标方法
                icon_data = self.get_default_app_icon(package_name)
                if icon_data:
                    self.app_icon_loaded.emit(package_name, icon_data)
                
    def get_app_name(self, package_name):
        """获取应用的真实名称"""
        try:
            # 使用aapt命令获取应用名称（如果安装了aapt工具）
            aapt_cmd = f"shell pm path {package_name}"
            path_result = self.controller.execute_adb_command(aapt_cmd, self.device_id)
            
            if path_result[0] and path_result[1] and path_result[1].startswith("package:"):
                apk_path = path_result[1].strip().replace("package:", "")
                
                # 尝试从APK中提取应用标签
                label_cmd = f"shell dumpsys package {package_name} | grep -E 'applicationInfo|labelRes|nonLocalizedLabel'"
                label_result = self.controller.execute_adb_command(label_cmd, self.device_id)
                
                if label_result[0] and label_result[1]:
                    # 尝试从结果中提取非本地化标签
                    for line in label_result[1].split('\n'):
                        if "nonLocalizedLabel=" in line:
                            parts = line.split("nonLocalizedLabel=")
                            if len(parts) > 1:
                                app_name = parts[1].split(' ')[0].strip()
                                if app_name and len(app_name) > 1:
                                    return app_name
            
            # 如果上面的方法不起作用，尝试从dumpsys package中提取标签（短标签）
            label_cmd = f"shell dumpsys package {package_name} | grep -E 'label=\"|labelRes='"
            label_result = self.controller.execute_adb_command(label_cmd, self.device_id)
            
            if label_result[0] and label_result[1]:
                for line in label_result[1].split('\n'):
                    if 'label="' in line:
                        label_start = line.find('label="') + 7
                        label_end = line.find('"', label_start)
                        if label_end > label_start:
                            app_name = line[label_start:label_end].strip()
                            if app_name and len(app_name) > 1:
                                return app_name
            
            # 尝试使用settings命令获取应用名称（仅适用于最新版本的Android）
            settings_cmd = f"shell settings get secure android.app.names.{package_name}"
            settings_result = self.controller.execute_adb_command(settings_cmd, self.device_id)
            
            if settings_result[0] and settings_result[1] and settings_result[1] != "null":
                app_name = settings_result[1].strip()
                if app_name and len(app_name) > 1 and app_name != "null":
                    return app_name
            
            # 返回默认名称
            return None
        except Exception as e:
            print(f"获取应用名称出错: {e}")
            return None

    def get_default_app_icon(self, package_name):
        """获取应用默认图标"""
        try:
            # 创建一个临时目录
            import tempfile
            temp_dir = tempfile.mkdtemp()
            
            # 创建简单的彩色图标
            from PIL import Image, ImageDraw, ImageFont
            
            # 使用包名的哈希值作为颜色种子
            import hashlib
            
            # 计算包名的哈希值
            hash_object = hashlib.md5(package_name.encode())
            hash_hex = hash_object.hexdigest()
            
            # 从哈希值中提取RGB颜色
            r = int(hash_hex[0:2], 16)
            g = int(hash_hex[2:4], 16)
            b = int(hash_hex[4:6], 16)
            
            # 创建一个彩色图标
            img = Image.new('RGBA', (192, 192), color=(255, 255, 255, 0))
            d = ImageDraw.Draw(img)
            
            # 绘制一个圆形图标，颜色基于包名
            d.ellipse((0, 0, 192, 192), fill=(r, g, b, 255))
            
            # 将首字母绘制在图标中心
            # 使用包名的首字母
            first_letter = package_name[0].upper()
            
            # 尝试加载字体，如果失败则使用默认方法
            try:
                # 使用系统默认字体
                font = ImageFont.truetype("arial.ttf", 72)
                d.text((80, 60), first_letter, fill=(255, 255, 255, 255), font=font)
            except:
                # 如果无法加载字体，使用简单的绘制方法
                d.text((80, 60), first_letter, fill=(255, 255, 255, 255))
            
            # 保存到临时文件
            temp_icon_path = os.path.join(temp_dir, f"{package_name}.png")
            img.save(temp_icon_path, format="PNG")
            
            # 读取图标数据
            with open(temp_icon_path, 'rb') as f:
                icon_data = f.read()
                
            # 清理临时文件
            try:
                os.unlink(temp_icon_path)
                os.rmdir(temp_dir)
            except:
                pass
            
            return icon_data
        except Exception as e:
            print(f"创建应用图标出错: {e}")
            return None
                    

class AppActionThread(QThread):
    """执行应用操作的后台线程"""
    action_result = pyqtSignal(bool, str)
    
    def __init__(self, controller, device_id, package_name, action):
        super().__init__()
        self.controller = controller
        self.device_id = device_id
        self.package_name = package_name
        self.action = action
        
    def run(self):
        # 根据操作类型执行不同的命令
        try:
            if self.action == "start":
                # 启动应用，使用monkey命令
                cmd = f"shell monkey -p {self.package_name} -c android.intent.category.LAUNCHER 1"
                result = self.controller.execute_adb_command(cmd, self.device_id)
                if result[0]:
                    self.action_result.emit(True, f"已启动应用 {self.package_name}")
                else:
                    self.action_result.emit(False, f"启动应用失败: {result[1]}")
                
            elif self.action == "stop":
                # 停止应用，使用force-stop命令
                cmd = f"shell am force-stop {self.package_name}"
                result = self.controller.execute_adb_command(cmd, self.device_id)
                if result[0]:
                    self.action_result.emit(True, f"已停止应用 {self.package_name}")
                else:
                    self.action_result.emit(False, f"停止应用失败: {result[1]}")
            
            elif self.action == "uninstall":
                # 卸载应用
                cmd = f"uninstall {self.package_name}"
                result = self.controller.execute_adb_command(cmd, self.device_id)
                if result[0]:
                    self.action_result.emit(True, f"已卸载应用 {self.package_name}")
                else:
                    self.action_result.emit(False, f"卸载应用失败: {result[1]}")
                    
        except Exception as e:
            self.action_result.emit(False, f"操作执行错误: {str(e)}")


class AppManagerDialog(QDialog):
    """应用管理器对话框"""
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.selected_device = None
        self.selected_package = None
        self.app_icons = {}  # 保存应用图标缓存
        self.app_list = []  # 保存应用列表
        
        self.setWindowTitle("应用管理器")
        self.resize(800, 600)
        
        self.setup_ui()
        
        # 刷新设备列表
        self.refresh_devices()
        
    def setup_ui(self):
        """设置UI组件"""
        # 创建主布局
        main_layout = QVBoxLayout(self)
        
        # 设备选择区域
        device_group = QGroupBox("设备选择")
        device_layout = QHBoxLayout(device_group)
        
        device_layout.addWidget(QLabel("设备:"))
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(300)
        self.device_combo.currentIndexChanged.connect(self.on_device_changed)
        device_layout.addWidget(self.device_combo, 1)
        
        self.refresh_btn = QPushButton("刷新设备")
        self.refresh_btn.clicked.connect(self.refresh_devices)
        device_layout.addWidget(self.refresh_btn)
        
        main_layout.addWidget(device_group)
        
        # 创建应用列表和详情的分割面板
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        
        # 应用列表区域
        app_list_group = QGroupBox("已安装应用")
        app_list_layout = QVBoxLayout(app_list_group)
        
        # 添加过滤和选项
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("搜索:"))
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("输入关键字筛选应用")
        self.filter_input.textChanged.connect(self.filter_apps)
        filter_layout.addWidget(self.filter_input, 1)
        
        self.show_system_cb = QCheckBox("显示系统应用")
        self.show_system_cb.setChecked(False)
        self.show_system_cb.stateChanged.connect(self.reload_apps)
        filter_layout.addWidget(self.show_system_cb)
        
        app_list_layout.addLayout(filter_layout)
        
        # 应用列表
        self.app_list_widget = QListWidget()
        self.app_list_widget.setIconSize(QSize(48, 48))
        self.app_list_widget.currentItemChanged.connect(self.on_app_selected)
        app_list_layout.addWidget(self.app_list_widget, 1)
        
        # 添加加载进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        app_list_layout.addWidget(self.progress_bar)
        
        # 操作按钮区域
        action_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("启动")
        self.start_btn.clicked.connect(lambda: self.perform_app_action("start"))
        self.start_btn.setEnabled(False)
        action_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("停止")
        self.stop_btn.clicked.connect(lambda: self.perform_app_action("stop"))
        self.stop_btn.setEnabled(False)
        action_layout.addWidget(self.stop_btn)
        
        self.uninstall_btn = QPushButton("卸载")
        self.uninstall_btn.clicked.connect(lambda: self.perform_app_action("uninstall"))
        self.uninstall_btn.setEnabled(False)
        action_layout.addWidget(self.uninstall_btn)
        
        self.info_btn = QPushButton("查看信息")
        self.info_btn.clicked.connect(self.show_app_info)
        self.info_btn.setEnabled(False)
        action_layout.addWidget(self.info_btn)
        
        app_list_layout.addLayout(action_layout)
        
        # 应用详情区域
        app_detail_group = QGroupBox("应用详情")
        app_detail_layout = QVBoxLayout(app_detail_group)
        
        # 使用选项卡组织详情内容
        self.detail_tabs = QTabWidget()
        
        # 基本信息选项卡
        basic_info_tab = QWidget()
        basic_info_layout = QVBoxLayout(basic_info_tab)
        self.app_info_text = QTextEdit()
        self.app_info_text.setReadOnly(True)
        basic_info_layout.addWidget(self.app_info_text)
        self.detail_tabs.addTab(basic_info_tab, "基本信息")
        
        # 日志选项卡
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        
        log_btn_layout = QHBoxLayout()
        self.clear_log_btn = QPushButton("清空日志")
        self.clear_log_btn.clicked.connect(self.log_text.clear)
        log_btn_layout.addWidget(self.clear_log_btn)
        log_layout.addLayout(log_btn_layout)
        
        self.detail_tabs.addTab(log_tab, "操作日志")
        
        app_detail_layout.addWidget(self.detail_tabs)
        
        # 添加到分割器
        splitter.addWidget(app_list_group)
        splitter.addWidget(app_detail_group)
        splitter.setSizes([300, 500])  # 设置初始大小比例
        
        main_layout.addWidget(splitter, 1)
        
        # 底部按钮区域
        button_layout = QHBoxLayout()
        
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.close)
        button_layout.addStretch(1)
        button_layout.addWidget(self.close_btn)
        
        main_layout.addLayout(button_layout)
        
    def refresh_devices(self):
        """刷新设备列表"""
        self.device_combo.clear()
        self.app_list_widget.clear()
        self.app_info_text.clear()
        
        # 禁用操作按钮
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.uninstall_btn.setEnabled(False)
        self.info_btn.setEnabled(False)
        
        try:
            devices = self.controller.get_devices()
            
            if not devices:
                self.log("未检测到设备")
                return
                
            for device_id, model in devices:
                self.device_combo.addItem(f"{model} ({device_id})", device_id)
                
            if self.device_combo.count() > 0:
                self.device_combo.setCurrentIndex(0)
                
        except Exception as e:
            self.log(f"刷新设备列表出错: {e}")
            
    def on_device_changed(self, index):
        """设备选择改变处理"""
        self.app_list_widget.clear()
        self.app_info_text.clear()
        
        if index >= 0:
            self.selected_device = self.device_combo.currentData()
            self.log(f"已选择设备: {self.selected_device}")
            
            # 加载应用列表
            self.load_app_list()
        else:
            self.selected_device = None
            
    def get_current_device(self):
        """获取当前选择的设备ID"""
        if self.device_combo.currentIndex() >= 0:
            return self.device_combo.currentData()
        return None
            
    def load_app_list(self):
        """加载应用列表"""
        device_id = self.get_current_device()
        if not device_id:
            self.log("请先选择一个设备")
            return
            
        # 清空列表和缓存
        self.app_list_widget.clear()
        self.app_list = []
        self.app_icons = {}
        
        # 显示进度条
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        
        # 在后台线程中加载
        self.app_list_thread = AppListThread(
            self.controller, 
            device_id,
            self.show_system_cb.isChecked()
        )
        self.app_list_thread.app_loaded.connect(self.update_app_list)
        self.app_list_thread.loading_progress.connect(self.update_loading_progress)
        self.app_list_thread.app_icon_loaded.connect(self.update_app_icon)
        self.app_list_thread.start()
        
    def update_loading_progress(self, current, total):
        """更新加载进度"""
        percent = (current / total) * 100 if total > 0 else 0
        self.progress_bar.setValue(int(percent))
        
    def update_app_icon(self, package_name, icon_data):
        """更新应用图标"""
        try:
            # 将图标数据转换为QPixmap
            pixmap = QPixmap()
            pixmap.loadFromData(icon_data)
            
            # 创建图标对象
            icon = QIcon(pixmap)
            
            # 保存到缓存
            self.app_icons[package_name] = icon
            
            # 更新列表项图标
            for i in range(self.app_list_widget.count()):
                item = self.app_list_widget.item(i)
                data = item.data(Qt.UserRole)
                if data == package_name:
                    item.setIcon(icon)
                    break
        except Exception as e:
            print(f"更新应用图标出错: {e}")
        
    def update_app_list(self, app_list):
        """更新应用列表"""
        self.app_list = app_list
        self.app_list_widget.clear()
        
        if not app_list:
            self.log("没有找到应用")
            self.progress_bar.setVisible(False)
            return
        
        # 添加应用到列表
        for display_name, package_name in app_list:
            item = QListWidgetItem(display_name)
            item.setData(Qt.UserRole, package_name)
            item.setToolTip(package_name)
            
            # 设置默认图标
            default_icon = QIcon.fromTheme("application-x-executable")
            if default_icon.isNull():
                # 使用系统默认图标
                default_icon = self.style().standardIcon(self.style().SP_FileIcon)
            item.setIcon(default_icon)
            
            # 如果已有图标则设置
            if package_name in self.app_icons:
                item.setIcon(self.app_icons[package_name])
                
            self.app_list_widget.addItem(item)
            
        self.log(f"已加载 {len(app_list)} 个应用")
        self.progress_bar.setVisible(False)
        
    def reload_apps(self):
        """重新加载应用列表"""
        self.load_app_list()
        
    def filter_apps(self):
        """根据输入过滤应用列表"""
        filter_text = self.filter_input.text().lower()
        for i in range(self.app_list_widget.count()):
            item = self.app_list_widget.item(i)
            display_name = item.text().lower()
            package_name = item.data(Qt.UserRole).lower()
            item.setHidden(filter_text and not (filter_text in display_name or filter_text in package_name))
            
    def on_app_selected(self):
        """应用选择改变处理"""
        current_item = self.app_list_widget.currentItem()
        if current_item:
            self.selected_package = current_item.data(Qt.UserRole)
            
            # 更新应用信息
            self.app_info_text.setText(
                f"应用名称: {current_item.text()}\n"
                f"包名: {self.selected_package}\n"
                f"设备: {self.selected_device}\n"
            )
            
            # 启用操作按钮
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(True)
            self.uninstall_btn.setEnabled(True)
            self.info_btn.setEnabled(True)
        else:
            self.selected_package = None
            self.app_info_text.clear()
            
            # 禁用操作按钮
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
            self.uninstall_btn.setEnabled(False)
            self.info_btn.setEnabled(False)
        
    def perform_app_action(self, action):
        """执行应用操作"""
        if not self.selected_device or not self.selected_package:
            self.log("请先选择设备和应用")
            return
            
        # 确认卸载
        if action == "uninstall":
            reply = QMessageBox.question(
                self,
                "确认卸载",
                f"确定要卸载应用 {self.selected_package} 吗？\n此操作不可恢复！",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
                
        # 显示操作信息
        action_descriptions = {
            "start": "启动",
            "stop": "停止",
            "uninstall": "卸载"
        }
        
        description = action_descriptions.get(action, action)
        self.log(f"正在{description}应用 {self.selected_package}...")
        
        # 禁用操作按钮
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.uninstall_btn.setEnabled(False)
        self.info_btn.setEnabled(False)
        
        # 在后台线程中执行操作
        self.action_thread = AppActionThread(
            self.controller,
            self.selected_device,
            self.selected_package,
            action
        )
        self.action_thread.action_result.connect(self.handle_action_result)
        self.action_thread.start()
        
    def handle_action_result(self, success, output):
        """处理操作结果"""
        self.log(output)
        
        # 如果是卸载操作且成功，则从列表中移除
        if success and self.selected_package and output.startswith("已卸载应用"):
            for i in range(self.app_list_widget.count()):
                item = self.app_list_widget.item(i)
                if item.data(Qt.UserRole) == self.selected_package:
                    self.app_list_widget.takeItem(i)
                    break
            self.app_info_text.clear()
            self.selected_package = None
        
        # 重新加载应用列表
        if success and self.selected_device:
            QTimer.singleShot(1000, self.reload_apps)
        
        # 重新启用操作按钮
        if self.selected_package:
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(True)
            self.uninstall_btn.setEnabled(True)
            self.info_btn.setEnabled(True)
            
    def show_app_info(self):
        """显示应用详细信息"""
        if not self.selected_device or not self.selected_package:
            return
            
        # 获取应用信息
        cmd = f"shell dumpsys package {self.selected_package}"
        result = self.controller.execute_adb_command(cmd, self.selected_device)
        
        if result[0] and result[1]:
            # 创建新窗口显示信息
            info_dialog = QDialog(self)
            info_dialog.setWindowTitle(f"应用信息 - {self.selected_package}")
            info_dialog.resize(800, 600)
            
            layout = QVBoxLayout(info_dialog)
            
            # 文本编辑器显示信息
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setPlainText(result[1])
            layout.addWidget(text_edit)
            
            # 关闭按钮
            btn_layout = QHBoxLayout()
            close_btn = QPushButton("关闭")
            close_btn.clicked.connect(info_dialog.close)
            btn_layout.addStretch(1)
            btn_layout.addWidget(close_btn)
            layout.addLayout(btn_layout)
            
            info_dialog.exec_()
        else:
            self.log(f"获取应用信息失败: {result[1]}")
            
    def log(self, message):
        """向日志中添加消息"""
        # 添加时间戳
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        
        # 滚动到底部
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


if __name__ == "__main__":
    # 独立运行时的代码
    app = QApplication(sys.argv)
    
    from scrcpy_controller import ScrcpyController
    controller = ScrcpyController()
    
    dialog = AppManagerDialog(None, controller)
    dialog.show()
    
    sys.exit(app.exec_()) 