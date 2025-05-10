#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import subprocess
import time
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QLabel, 
    QComboBox, QPushButton, QLineEdit, QFileDialog, QMessageBox, QTextEdit,
    QAction, QMenu, QMenuBar, QFrame, QCheckBox, QGroupBox, QGridLayout
)
from PyQt5.QtCore import Qt, QProcess, QTimer
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
        
        # 上次日志消息，用于避免重复
        self.last_log_message = ""
        self.repeat_count = 0
        
        # 创建控制器
        self.controller = ScrcpyController()
        
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
        
        self.check_devices()
        
        # 创建定时器，定期检查设备
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_devices)
        self.timer.start(3000)  # 每3秒检查一次设备
        
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
            # 尝试通过环境变量PATH查找
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creationflags = subprocess.CREATE_NO_WINDOW
                # 在Windows下尝试查找
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
                os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Android', 'Sdk', 'platform-tools', 'adb.exe'),
                os.path.join(os.environ.get('ANDROID_HOME', ''), 'platform-tools', 'adb.exe'),
                os.path.join(os.environ.get('ANDROID_SDK_ROOT', ''), 'platform-tools', 'adb.exe'),
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
            # 尝试通过环境变量PATH查找
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
        refresh_btn.clicked.connect(self.check_devices)
        
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
        self.auto_refresh_cb.setChecked(True)
        
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
        options_layout = QHBoxLayout(options_group)
        
        self.record_cb = QCheckBox("录制屏幕")
        self.fullscreen_cb = QCheckBox("全屏显示")
        self.always_top_cb = QCheckBox("窗口置顶")
        self.show_touches_cb = QCheckBox("显示触摸")
        self.no_control_cb = QCheckBox("无交互")
        self.disable_clipboard_cb = QCheckBox("禁用剪贴板")
        
        options_layout.addWidget(self.record_cb)
        options_layout.addWidget(self.fullscreen_cb)
        options_layout.addWidget(self.always_top_cb)
        options_layout.addWidget(self.show_touches_cb)
        options_layout.addWidget(self.no_control_cb)
        options_layout.addWidget(self.disable_clipboard_cb)
        
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
        
    def create_menus(self):
        """创建菜单栏"""
        menu_bar = self.menuBar()
        
        # 设备菜单
        device_menu = menu_bar.addMenu("设备")
        
        refresh_action = QAction("刷新设备列表", self)
        refresh_action.triggered.connect(self.check_devices)
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
            
    def check_devices(self):
        """检查连接的设备并更新设备列表"""
        try:
            devices = self.controller.get_devices()
            
            # 清空当前列表
            self.device_combo.clear()
            
            for device_id, model in devices:
                self.device_combo.addItem(f"{model} ({device_id})", device_id)
            
            # 更新连接按钮状态
            has_devices = self.device_combo.count() > 0
            self.usb_btn.setEnabled(has_devices)
            self.wifi_btn.setEnabled(has_devices)
            self.connect_all_btn.setEnabled(has_devices and len(devices) > 1)
            
            if not has_devices and self.auto_refresh_cb.isChecked():
                self.log("未检测到设备，请检查设备连接")
            elif has_devices and not self.device_combo.currentText():
                self.device_combo.setCurrentIndex(0)
                self.log(f"检测到 {len(devices)} 个设备")
            
            return devices
        except Exception as e:
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
            
        # 设置窗口标题为设备型号
        device_model = self.device_combo.currentText().split(' (')[0]
        window_title = f"{device_model} - {device_id}"
        cmd.extend(['--window-title', window_title])
            
        # 启动进程
        self.log(f"启动设备 {device_id} 镜像: {' '.join(cmd)}")
        
        try:
            # 创建进程
            process = QProcess()
            process.readyReadStandardOutput.connect(lambda proc=process, dev=device_id: self.handle_process_output(proc, dev))
            process.readyReadStandardError.connect(lambda proc=process, dev=device_id: self.handle_process_error(proc, dev))
            process.finished.connect(lambda exitCode, exitStatus, dev=device_id: self.handle_process_finished(dev))
            
            # 保存进程
            self.device_processes[device_id] = process
            
            # 启动进程
            process.start(cmd[0], cmd[1:])
            self.log(f"已启动设备 {device_id} 的 scrcpy 进程")
        except Exception as e:
            self.log(f"启动 scrcpy 失败: {str(e)}")
            if device_id in self.device_processes:
                del self.device_processes[device_id]
                
    def stop_scrcpy(self):
        """停止scrcpy进程"""
        # 如果没有选择设备，停止所有进程
        if self.device_combo.currentIndex() < 0:
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
            
    def log(self, message):
        """向日志文本框中添加消息"""
        if not message:
            return
            
        # 添加时间戳
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        # 处理重复消息
        if message == self.last_log_message:
            self.repeat_count += 1
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
        
        # 滚动到底部
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
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
                
            # 添加窗口位置偏移，避免所有窗口重叠
            # 将窗口均匀分布在屏幕上 (使用更智能的排列方式)
            columns = max(1, int(device_count ** 0.5))  # 根据设备数量计算合适的列数
            row = count // columns
            col = count % columns
            x_offset = col * 320  # 每个窗口水平间隔320像素
            y_offset = row * 240  # 每个窗口垂直间隔240像素
            
            cmd.extend(['--window-x', str(x_offset + 50)])  # 加上50像素的初始边距
            cmd.extend(['--window-y', str(y_offset + 50)])
            
            # 设置窗口标题
            window_title = f"{model} - {device_id}"
            cmd.extend(['--window-title', window_title])
            
            # 添加其他选项，与单设备启动保持一致
            if self.show_touches_cb.isChecked():
                cmd.append('--show-touches')
                
            # 重要：确保不启用无交互模式，除非用户特别指定
            if not self.no_control_cb.isChecked():
                # 确保可以控制设备
                pass  # 不添加--no-control参数
            else:
                # 用户特意选择了无交互模式
                cmd.append('--no-control')
                
            if self.disable_clipboard_cb.isChecked():
                cmd.append('--no-clipboard-autosync')
                
            # 添加方向控制
            rotation_option = self.rotation_combo.currentText()
            if rotation_option == "横屏":
                cmd.append('--lock-video-orientation=0')
            elif rotation_option == "竖屏":
                cmd.append('--lock-video-orientation=1')
            
            # 如果设置了全屏模式则添加参数
            if self.fullscreen_cb.isChecked() and device_count == 1:
                # 只有在单设备模式下才启用全屏
                cmd.append('--fullscreen')
                
            # 如果设置了窗口置顶则添加参数
            if self.always_top_cb.isChecked():
                cmd.append('--always-on-top')
            
            # 在Windows平台上，确保允许窗口移动
            # --window-borderless 是一个不接受参数的标志选项
            # 默认情况下窗口是有边框的，所以不添加此参数
            # 如果要无边框，才需要添加 --window-borderless
            
            try:
                # 创建进程
                process = QProcess()
                process.readyReadStandardOutput.connect(lambda proc=process, dev=device_id: self.handle_process_output(proc, dev))
                process.readyReadStandardError.connect(lambda proc=process, dev=device_id: self.handle_process_error(proc, dev))
                process.finished.connect(lambda exitCode, exitStatus, dev=device_id: self.handle_process_finished(dev))
                
                # 保存进程
                self.device_processes[device_id] = process
                
                # 启动进程
                process.start(cmd[0], cmd[1:])
                self.log(f"已启动设备 {model} ({device_id}) 的 scrcpy 进程，命令: {' '.join(cmd)}")
                count += 1
                
                # 每个设备启动后稍微等待一下，避免系统资源争用
                if count < len(devices):
                    QTimer.singleShot(1000, lambda: self.log("等待下一个设备启动..."))
                    time.sleep(1.0)  # 暂停1秒
                
            except Exception as e:
                self.log(f"启动设备 {model} ({device_id}) 失败: {str(e)}")
                if device_id in self.device_processes:
                    del self.device_processes[device_id]
                    
        if count > 0:
            self.log(f"成功连接 {count} 个设备")
            
            # 提示用户如何移动窗口
            if count > 1:
                QMessageBox.information(
                    self, 
                    "多设备连接成功", 
                    f"成功连接 {count} 个设备。\n\n"
                    "您可以拖动窗口标题栏移动每个设备窗口的位置。\n"
                    "使用Alt+左键可以调整窗口大小。\n"
                    "使用鼠标右键可以返回上一步。"
                )
    
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