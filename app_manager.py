#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QWidget, 
    QPushButton, QLabel, QListWidget, QListWidgetItem, QComboBox,
    QMessageBox, QGridLayout, QGroupBox, QLineEdit, QProgressBar,
    QSplitter, QTabWidget, QTextEdit
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import QIcon, QPixmap, QFont

"""
简化版应用管理器，用于管理和操作Android设备上的应用程序。

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
            print(f"生成默认图标错误: {e}")
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
        if self.action == "start":
            cmd = f"shell monkey -p {self.package_name} -c android.intent.category.LAUNCHER 1"
        elif self.action == "stop":
            cmd = f"shell am force-stop {self.package_name}"
        elif self.action == "uninstall":
            cmd = f"uninstall {self.package_name}"
        else:
            self.action_result.emit(False, f"未知操作: {self.action}")
            return
            
        # 执行命令
        result = self.controller.execute_adb_command(cmd, self.device_id)
        
        # 处理结果
        if result[0]:
            self.action_result.emit(True, f"成功{self.action}应用: {self.package_name}")
        else:
            self.action_result.emit(False, f"执行{self.action}失败: {result[1]}")

class AppManagerDialog(QDialog):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.parent = parent
        self.app_icons = {}  # 存储应用图标的字典: 包名 -> 图标数据
        
        # 初始化界面
        self.setup_ui()
        
        # 获取设备列表
        self.refresh_devices()
        
    def setup_ui(self):
        self.setWindowTitle("应用管理器")
        self.resize(800, 600)  # 增大窗口尺寸
        
        # 主布局
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 设备选择区域
        device_group = QGroupBox("设备选择")
        device_layout = QHBoxLayout(device_group)
        
        self.device_label = QLabel("设备:")
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(250)
        self.device_combo.currentIndexChanged.connect(self.on_device_changed)
        
        refresh_btn = QPushButton("刷新设备")
        refresh_btn.clicked.connect(self.refresh_devices)
        
        device_layout.addWidget(self.device_label)
        device_layout.addWidget(self.device_combo, 1)
        device_layout.addWidget(refresh_btn)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        
        # 应用列表页面
        app_tab = QWidget()
        app_layout = QVBoxLayout(app_tab)
        
        # 搜索过滤
        filter_layout = QHBoxLayout()
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("搜索应用...")
        self.filter_input.textChanged.connect(self.filter_apps)
        
        filter_layout.addWidget(QLabel("筛选:"))
        filter_layout.addWidget(self.filter_input, 1)
        
        # 显示系统应用选项
        self.show_system_check = QComboBox()
        self.show_system_check.addItems(["仅用户应用", "所有应用"])
        self.show_system_check.currentIndexChanged.connect(self.reload_apps)
        
        filter_layout.addWidget(self.show_system_check)
        
        # 刷新应用列表按钮
        refresh_apps_btn = QPushButton("刷新应用")
        refresh_apps_btn.clicked.connect(self.reload_apps)
        filter_layout.addWidget(refresh_apps_btn)
        
        app_layout.addLayout(filter_layout)
        
        # 应用列表
        self.app_list = QListWidget()
        self.app_list.setIconSize(QSize(36, 36))  # 设置图标大小
        self.app_list.itemSelectionChanged.connect(self.on_app_selected)
        app_layout.addWidget(self.app_list)
        
        # 加载进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        app_layout.addWidget(self.progress_bar)
        
        # 应用操作按钮区域
        action_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("启动应用")
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(lambda: self.perform_app_action("start"))
        
        self.stop_btn = QPushButton("停止应用")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(lambda: self.perform_app_action("stop"))
        
        self.uninstall_btn = QPushButton("卸载应用")
        self.uninstall_btn.setEnabled(False)
        self.uninstall_btn.clicked.connect(lambda: self.perform_app_action("uninstall"))
        
        # 添加更多功能按钮
        self.info_btn = QPushButton("应用信息")
        self.info_btn.setEnabled(False)
        self.info_btn.clicked.connect(self.show_app_info)
        
        action_layout.addWidget(self.start_btn)
        action_layout.addWidget(self.stop_btn)
        action_layout.addWidget(self.info_btn)
        action_layout.addWidget(self.uninstall_btn)
        
        app_layout.addLayout(action_layout)
        
        # 添加标签页
        self.tab_widget.addTab(app_tab, "应用列表")
        
        # 添加组件到主布局
        layout.addWidget(device_group)
        layout.addWidget(self.tab_widget, 1)
        
        # 状态标签
        self.status_label = QLabel("准备就绪")
        self.status_label.setStyleSheet("color: #4287f5; font-weight: bold;")
        layout.addWidget(self.status_label)
        
    def refresh_devices(self):
        """刷新设备列表"""
        # 获取设备列表
        devices = self.controller.get_devices()
        
        # 保存当前选中的设备ID
        current_device_id = self.device_combo.currentData() if self.device_combo.count() > 0 else None
        
        # 清空当前列表
        self.device_combo.clear()
        
        # 更新设备列表
        for device_id, model in devices:
            self.device_combo.addItem(f"{model} ({device_id})", device_id)
            
        # 检查是否有设备
        if self.device_combo.count() > 0:
            # 如果之前有选中的设备，尝试恢复选择
            if current_device_id:
                for i in range(self.device_combo.count()):
                    if self.device_combo.itemData(i) == current_device_id:
                        self.device_combo.setCurrentIndex(i)
                        break
            self.status_label.setText(f"已找到 {self.device_combo.count()} 个设备")
        else:
            self.status_label.setText("未发现设备，请检查连接")
            
    def on_device_changed(self, index):
        """设备选择变更"""
        if index >= 0:
            # 加载应用列表
            self.load_app_list()
        else:
            # 清空应用列表
            self.app_list.clear()
            
    def get_current_device(self):
        """获取当前选择的设备ID"""
        index = self.device_combo.currentIndex()
        if index >= 0:
            return self.device_combo.itemData(index)
        return None
        
    def load_app_list(self):
        """加载应用列表"""
        device_id = self.get_current_device()
        if not device_id:
            return
            
        # 清空列表
        self.app_list.clear()
        
        # 显示加载进度条
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # 设置状态
        self.status_label.setText("正在加载应用列表...")
        
        # 是否显示系统应用
        show_system = self.show_system_check.currentIndex() == 1
        
        # 创建线程加载应用列表
        self.app_list_thread = AppListThread(self.controller, device_id, show_system)
        self.app_list_thread.app_loaded.connect(self.update_app_list)
        self.app_list_thread.loading_progress.connect(self.update_loading_progress)
        self.app_list_thread.app_icon_loaded.connect(self.update_app_icon)
        self.app_list_thread.start()
        
    def update_loading_progress(self, current, total):
        """更新加载进度"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        
    def update_app_icon(self, package_name, icon_data):
        """更新应用图标"""
        if not icon_data:
            return
            
        self.app_icons[package_name] = icon_data
        
        # 更新列表项的图标
        for i in range(self.app_list.count()):
            item = self.app_list.item(i)
            if item.data(Qt.UserRole) == package_name:
                pixmap = QPixmap()
                pixmap.loadFromData(icon_data)
                item.setIcon(QIcon(pixmap))
                break
    
    def update_app_list(self, app_list):
        """更新应用列表"""
        # 隐藏进度条
        self.progress_bar.setVisible(False)
        
        # 清空列表
        self.app_list.clear()
        
        # 添加应用到列表
        for display_name, package_name in app_list:
            if display_name == package_name.split('.')[-1].capitalize():
                # 如果只有默认名称，只显示包名
                item = QListWidgetItem(f"{package_name}")
            else:
                # 如果有应用名称，同时显示应用名称和包名
                item = QListWidgetItem(f"{display_name}\n{package_name}")
                
                # 设置字体样式
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            
            # 设置固定高度
            item.setSizeHint(QSize(item.sizeHint().width(), 48))
            
            # 设置图标
            if package_name in self.app_icons:
                pixmap = QPixmap()
                pixmap.loadFromData(self.app_icons[package_name])
                item.setIcon(QIcon(pixmap))
            
            item.setData(Qt.UserRole, package_name)
            self.app_list.addItem(item)
            
        # 更新状态
        self.status_label.setText(f"已加载 {len(app_list)} 个应用")
        
    def reload_apps(self):
        """重新加载应用列表"""
        self.load_app_list()
        
    def filter_apps(self):
        """筛选应用列表"""
        filter_text = self.filter_input.text().lower()
        
        for i in range(self.app_list.count()):
            item = self.app_list.item(i)
            item.setHidden(filter_text and filter_text not in item.text().lower())
            
    def on_app_selected(self):
        """应用选择变更"""
        # 获取选中项
        selected_items = self.app_list.selectedItems()
        
        # 启用/禁用按钮
        has_selection = len(selected_items) > 0
        self.start_btn.setEnabled(has_selection)
        self.stop_btn.setEnabled(has_selection)
        self.uninstall_btn.setEnabled(has_selection)
        self.info_btn.setEnabled(has_selection)  # 同时启用应用信息按钮
        
    def perform_app_action(self, action):
        """执行应用操作"""
        # 获取当前设备
        device_id = self.get_current_device()
        if not device_id:
            self.status_label.setText("未找到设备")
            return
            
        # 获取选中的应用
        selected_items = self.app_list.selectedItems()
        if not selected_items:
            self.status_label.setText("未选择应用")
            return
            
        # 获取选中的包名
        package_name = selected_items[0].data(Qt.UserRole)
        
        # 确认卸载操作
        if action == "uninstall":
            reply = QMessageBox.question(
                self, 
                "确认卸载", 
                f"确定要卸载应用 {package_name} 吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
                
        # 更新状态
        self.status_label.setText(f"正在{action}应用...")
        
        # 禁用按钮
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.uninstall_btn.setEnabled(False)
        
        # 创建线程执行操作
        self.action_thread = AppActionThread(self.controller, device_id, package_name, action)
        self.action_thread.action_result.connect(self.handle_action_result)
        self.action_thread.start()
        
    def handle_action_result(self, success, output):
        """处理操作结果"""
        # 更新状态
        self.status_label.setText(output)
        
        # 如果是卸载操作且成功，刷新应用列表
        if "uninstall" in output.lower() and success:
            self.reload_apps()
            
        # 重新启用按钮
        self.on_app_selected()

    def show_app_info(self):
        """显示应用详细信息"""
        # 获取当前设备
        device_id = self.get_current_device()
        if not device_id:
            self.status_label.setText("未找到设备")
            return
            
        # 获取选中的应用
        selected_items = self.app_list.selectedItems()
        if not selected_items:
            self.status_label.setText("未选择应用")
            return
            
        # 获取选中的包名
        package_name = selected_items[0].data(Qt.UserRole)
        
        # 显示正在加载信息
        self.status_label.setText(f"正在加载 {package_name} 的详细信息...")
        
        # 创建等待对话框
        info_dialog = QDialog(self)
        info_dialog.setWindowTitle(f"应用信息 - {package_name}")
        info_dialog.resize(700, 500)
        
        layout = QVBoxLayout(info_dialog)
        
        # 加载图标和基本信息
        header_layout = QHBoxLayout()
        
        # 图标显示
        icon_label = QLabel()
        icon_label.setFixedSize(64, 64)
        
        # 如果有图标，显示图标
        if package_name in self.app_icons:
            pixmap = QPixmap()
            pixmap.loadFromData(self.app_icons[package_name])
            icon_label.setPixmap(pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        
        header_layout.addWidget(icon_label)
        
        # 应用基本信息
        info_label = QLabel(f"包名: {package_name}")
        info_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        header_layout.addWidget(info_label, 1)
        
        layout.addLayout(header_layout)
        
        # 创建选项卡
        tab_widget = QTabWidget()
        
        # 基本信息选项卡
        basic_tab = QWidget()
        basic_layout = QVBoxLayout(basic_tab)
        
        # 获取基本信息
        basic_info = QTextEdit()
        basic_info.setReadOnly(True)
        basic_layout.addWidget(basic_info)
        
        # 使用dumpsys获取应用信息
        cmd = f"shell dumpsys package {package_name} | grep -E 'versionName|firstInstallTime|lastUpdateTime|enabled|userId|targetSdk'"
        result = self.controller.execute_adb_command(cmd, device_id)
        
        if result[0] and result[1]:
            # 处理提取的信息
            info_text = "应用基本信息:\n\n"
            
            lines = result[1].split('\n')
            for line in lines:
                line = line.strip()
                if line:
                    info_text += f"{line}\n"
            
            basic_info.setText(info_text)
        else:
            basic_info.setText("无法获取应用基本信息")
        
        tab_widget.addTab(basic_tab, "基本信息")
        
        # 权限选项卡
        perm_tab = QWidget()
        perm_layout = QVBoxLayout(perm_tab)
        
        perm_info = QTextEdit()
        perm_info.setReadOnly(True)
        perm_layout.addWidget(perm_info)
        
        # 获取权限信息
        cmd = f"shell dumpsys package {package_name} | grep -A 50 'granted=true'"
        result = self.controller.execute_adb_command(cmd, device_id)
        
        if result[0] and result[1]:
            # 处理权限信息
            perm_text = "应用权限:\n\n"
            
            lines = result[1].split('\n')
            for line in lines:
                line = line.strip()
                if "permission." in line and "granted=" in line:
                    perm_text += f"{line}\n"
            
            perm_info.setText(perm_text)
        else:
            perm_info.setText("无法获取应用权限信息")
        
        tab_widget.addTab(perm_tab, "权限")
        
        # 活动选项卡
        activity_tab = QWidget()
        activity_layout = QVBoxLayout(activity_tab)
        
        activity_info = QTextEdit()
        activity_info.setReadOnly(True)
        activity_layout.addWidget(activity_info)
        
        # 获取活动信息
        cmd = f"shell dumpsys package {package_name} | grep -A 20 'Activities:'"
        result = self.controller.execute_adb_command(cmd, device_id)
        
        if result[0] and result[1]:
            activity_info.setText(f"应用活动:\n\n{result[1]}")
        else:
            activity_info.setText("无法获取应用活动信息")
        
        tab_widget.addTab(activity_tab, "活动")
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        
        # 打开应用按钮
        open_btn = QPushButton("启动应用")
        open_btn.clicked.connect(lambda: self.perform_app_action("start"))
        btn_layout.addWidget(open_btn)
        
        # 卸载应用按钮
        uninstall_btn = QPushButton("卸载应用")
        uninstall_btn.clicked.connect(lambda: self.perform_app_action("uninstall"))
        btn_layout.addWidget(uninstall_btn)
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(info_dialog.close)
        btn_layout.addWidget(close_btn)
        
        # 添加选项卡和按钮
        layout.addWidget(tab_widget)
        layout.addLayout(btn_layout)
        
        # 显示对话框
        self.status_label.setText("准备就绪")
        info_dialog.exec_()

if __name__ == "__main__":
    # 直接运行此文件时的测试代码
    app = QApplication(sys.argv)
    from scrcpy_controller import ScrcpyController
    controller = ScrcpyController()
    dialog = AppManagerDialog(None, controller)
    dialog.show()
    sys.exit(app.exec_()) 