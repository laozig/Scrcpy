#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import hashlib
import re
import shlex
import importlib
from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QWidget, 
    QPushButton, QLabel, QListWidget, QListWidgetItem, QComboBox,
    QMessageBox, QFileDialog, QGridLayout, QGroupBox, QLineEdit, QProgressBar,
    QSplitter, QTabWidget, QTextEdit, QCheckBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import QIcon, QPixmap

from device_service import DeviceService
from utils import console_log, load_settings, open_path, save_settings


_LAZY_PINYIN_SENTINEL = object()
_LAZY_PINYIN_CACHE = _LAZY_PINYIN_SENTINEL


def _get_lazy_pinyin():
    """按需加载 pypinyin，避免缺少依赖时影响主流程或触发打包噪音。"""
    global _LAZY_PINYIN_CACHE
    if _LAZY_PINYIN_CACHE is not _LAZY_PINYIN_SENTINEL:
        return _LAZY_PINYIN_CACHE
    try:
        module = importlib.import_module("pypinyin")
        _LAZY_PINYIN_CACHE = getattr(module, "lazy_pinyin", None)
    except Exception:
        _LAZY_PINYIN_CACHE = None
    return _LAZY_PINYIN_CACHE

"""
应用管理器，用于管理和操作Android设备上的应用程序。

功能：
1. 获取并显示已安装的应用列表
2. 启动、停止和卸载应用
3. 刷新设备列表和应用列表
"""


def build_search_tokens(text):
    """构建名称搜索用的原文 / 拼音 / 首字母 token。"""
    raw = (text or "").strip()
    normalized = raw.lower()
    initials = "".join(part[0] for part in re.split(r"\s+", normalized) if part)

    lazy_pinyin = _get_lazy_pinyin()
    if lazy_pinyin and raw:
        py_list = lazy_pinyin(raw)
        pinyin_full = "".join(py_list).lower()
        pinyin_initials = "".join(item[0] for item in py_list if item).lower()
    else:
        pinyin_full = normalized
        pinyin_initials = initials

    return {
        "normalized": normalized,
        "pinyin_full": pinyin_full,
        "pinyin_initials": pinyin_initials,
    }

class AppListThread(QThread):
    """加载应用列表的后台线程"""
    app_loaded = pyqtSignal(list)
    loading_progress = pyqtSignal(int, int)  # 当前数量、总数量
    app_icon_loaded = pyqtSignal(str, bytes)  # 包名, 图标字节数据
    
    def __init__(self, controller, device_id, show_system=False, load_icons=True, icon_prefetch_count=12, sort_by_name=True):
        super().__init__()
        self.controller = controller
        self.device_id = device_id
        self.show_system = show_system
        self.load_icons = load_icons
        self.icon_prefetch_count = icon_prefetch_count
        self.sort_by_name = sort_by_name
        self.icon_cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build", "app_icon_cache")
        os.makedirs(self.icon_cache_dir, exist_ok=True)
        
    def run(self):
        # 检查设备ID是否有效
        if not self.device_id:
            console_log("未找到设备ID，无法获取应用列表", "WARN")
            self.app_loaded.emit([])
            return

        all_packages = self._list_packages("shell cmd package list packages")
        if not all_packages:
            console_log("获取应用列表失败: 未返回任何包", "WARN")
            self.app_loaded.emit([])
            return
        user_packages = set(self._list_packages("shell cmd package list packages -3"))
            
        # 解析应用列表
        package_list = []
        package_names = list(all_packages)
        total_apps = len(package_names)

        for i, package_name in enumerate(package_names):
            self.loading_progress.emit(i+1, total_apps)
            display_name = package_name.split('.')[-1].capitalize()
            package_list.append({
                "display_name": display_name,
                "package_name": package_name,
                "is_system": package_name not in user_packages,
            })
        
        # 批量获取应用标签，减少多次 adb 调用
        if package_names:
            label_map = self.get_app_labels_bulk(package_names)
            if label_map:
                package_list = []
                for pkg in package_names:
                    name = label_map.get(pkg)
                    if not name:
                        name = pkg.split('.')[-1].capitalize()
                    search_tokens = build_search_tokens(name)
                    package_list.append({
                        "display_name": name,
                        "package_name": pkg,
                        "is_system": pkg not in user_packages,
                        "search_name": search_tokens["normalized"],
                        "search_pinyin": search_tokens["pinyin_full"],
                        "search_initials": search_tokens["pinyin_initials"],
                    })

        for item in package_list:
            if "search_name" not in item:
                search_tokens = build_search_tokens(item["display_name"])
                item["search_name"] = search_tokens["normalized"]
                item["search_pinyin"] = search_tokens["pinyin_full"]
                item["search_initials"] = search_tokens["pinyin_initials"]

        # 排序
        package_list.sort(key=(lambda x: x["display_name"]) if self.sort_by_name else (lambda x: x["package_name"]))
        console_log(f"找到应用数量: {len(package_list)}")
        self.app_loaded.emit(package_list)
        
        # 如果需要加载图标，在后台加载
        if self.load_icons and len(package_list) > 0 and self.icon_prefetch_count > 0:
            prefetch = min(self.icon_prefetch_count, len(package_list))
            for i, item in enumerate(package_list[:prefetch]):
                package_name = item["package_name"]
                # 使用默认图标方法
                icon_data = self.generate_icon_bytes(package_name)
                if icon_data:
                    self.app_icon_loaded.emit(package_name, icon_data)

    def _list_packages(self, command):
        result = self.controller.execute_adb_command(command, self.device_id)
        if not result[0] or not result[1]:
            return []

        packages = []
        for line in result[1].strip().split('\n'):
            line = line.strip()
            if line.startswith('package:'):
                packages.append(line[8:].strip())
        return packages
                
    def get_app_labels_bulk(self, package_names):
        """通过单次 dumpsys package 批量获取应用标签，提升加载速度"""
        try:
            if not package_names:
                return {}
            target_set = set(package_names)
            # 只用一次 dumpsys，尽量减少耗时
            cmd = "shell dumpsys package packages"
            result = self.controller.execute_adb_command(cmd, self.device_id)
            if not result[0] or not result[1]:
                return {}
            labels = {}
            current_pkg = None
            for line in result[1].splitlines():
                line = line.strip()
                if line.startswith("Package [") and "]" in line:
                    pkg = line.split("Package [", 1)[1].split("]", 1)[0]
                    current_pkg = pkg if pkg in target_set else None
                    continue
                if current_pkg:
                    # 优先 application-label- 开头（包含本地化），再退回 application-label:
                    if line.startswith("application-label-") and ":" in line:
                        label = line.split(":", 1)[1].strip().strip("'\"")
                        if label:
                            labels[current_pkg] = label
                            current_pkg = None
                            continue
                    if line.startswith("application-label:"):
                        label = line.split(":", 1)[1].strip().strip("'\"")
                        if label:
                            labels[current_pkg] = label
                            current_pkg = None
                            continue
            return labels
        except Exception as e:
            console_log(f"批量获取应用标签出错: {e}", "ERROR")
            return {}

    def generate_icon_bytes(self, package_name):
        """内存生成默认图标，避免临时文件开销"""
        try:
            cache_path = self._get_icon_cache_path(package_name)
            if os.path.exists(cache_path):
                with open(cache_path, 'rb') as f:
                    return f.read()

            from PIL import Image, ImageDraw, ImageFont
            import io

            hash_hex = hashlib.md5(package_name.encode()).hexdigest()
            r = int(hash_hex[0:2], 16)
            g = int(hash_hex[2:4], 16)
            b = int(hash_hex[4:6], 16)

            img = Image.new('RGBA', (192, 192), color=(255, 255, 255, 0))
            d = ImageDraw.Draw(img)
            d.ellipse((0, 0, 192, 192), fill=(r, g, b, 255))

            first_letter = package_name[0].upper()
            try:
                font = ImageFont.truetype("arial.ttf", 72)
                d.text((72, 56), first_letter, fill=(255, 255, 255, 255), font=font)
            except Exception:
                d.text((80, 60), first_letter, fill=(255, 255, 255, 255))

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            icon_bytes = buf.getvalue()
            with open(cache_path, 'wb') as f:
                f.write(icon_bytes)
            return icon_bytes
        except Exception as e:
            console_log(f"生成应用图标出错: {e}", "ERROR")
            return None

    def _get_icon_cache_path(self, package_name):
        digest = hashlib.md5(package_name.encode('utf-8')).hexdigest()
        return os.path.join(self.icon_cache_dir, f"{digest}.png")

class AppActionThread(QThread):
    """执行应用操作的后台线程"""
    action_result = pyqtSignal(bool, str)
    
    def __init__(self, controller, device_id, package_name, action, extra=None):
        super().__init__()
        self.controller = controller
        self.device_id = device_id
        self.package_name = package_name
        self.action = action
        self.extra = extra
        
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

            elif self.action == "clear_data":
                cmd = f"shell pm clear {self.package_name}"
                result = self.controller.execute_adb_command(cmd, self.device_id)
                if result[0]:
                    self.action_result.emit(True, f"已清除应用数据 {self.package_name}: {(result[1] or '').strip() or 'Success'}")
                else:
                    self.action_result.emit(False, f"清除应用数据失败: {result[1]}")

            elif self.action == "clear_cache":
                cmd = f"shell pm clear --cache-only {self.package_name}"
                result = self.controller.execute_adb_command(cmd, self.device_id)
                if result[0]:
                    self.action_result.emit(True, f"已尝试清除应用缓存 {self.package_name}: {(result[1] or '').strip() or 'Success'}")
                else:
                    self.action_result.emit(False, f"清除应用缓存失败: {result[1]}")

            elif self.action == "export_apk":
                output_path = self.extra
                path_result = self.controller.execute_adb_command(f"shell pm path {self.package_name}", self.device_id)
                if not path_result[0] or not path_result[1]:
                    self.action_result.emit(False, f"获取APK路径失败: {path_result[1]}")
                    return

                apk_path = None
                for line in path_result[1].splitlines():
                    if line.startswith("package:"):
                        apk_path = line.replace("package:", "").strip()
                        break
                if not apk_path:
                    self.action_result.emit(False, "未找到APK安装路径")
                    return

                pull_result = self.controller.execute_adb_command(["pull", apk_path, output_path], self.device_id)
                if pull_result[0]:
                    self.action_result.emit(True, f"已导出APK到: {output_path}")
                else:
                    self.action_result.emit(False, f"导出APK失败: {pull_result[1]}")
                    
        except Exception as e:
            self.action_result.emit(False, f"操作执行错误: {str(e)}")


class DeviceActionThread(QThread):
    """执行设备级动作，如安装 APK 或执行自定义 ADB 命令。"""
    action_result = pyqtSignal(str, bool, str)

    GLOBAL_COMMANDS = {
        "devices",
        "start-server",
        "kill-server",
        "connect",
        "disconnect",
        "install",
        "install-multiple",
        "version",
        "help",
        "host-features",
        "features",
        "reconnect",
    }

    def __init__(self, controller, device_id, action, extra=None):
        super().__init__()
        self.controller = controller
        self.device_id = device_id
        self.action = action
        self.extra = extra

    def _normalize_adb_command(self, command):
        if isinstance(command, str):
            raw_command = command.strip()
            if not raw_command:
                return [], None
            parts = shlex.split(raw_command)
        elif isinstance(command, (list, tuple)):
            parts = [str(part) for part in command if str(part).strip()]
        else:
            parts = [str(command).strip()] if str(command).strip() else []

        if parts and os.path.basename(parts[0]).lower() in ("adb", "adb.exe"):
            parts = parts[1:]

        explicit_device_id = None
        if len(parts) >= 2 and parts[0] == "-s":
            explicit_device_id = parts[1]
            parts = parts[2:]

        return parts, explicit_device_id

    def _resolve_device_for_command(self, command_parts, explicit_device_id=None):
        if explicit_device_id:
            return explicit_device_id
        if not command_parts:
            return None
        if command_parts[0].startswith("-"):
            return None
        if command_parts[0] in self.GLOBAL_COMMANDS:
            return None
        return self.device_id

    def run(self):
        try:
            if self.action == "install_apk":
                apk_path = str(self.extra or "").strip().strip('"')
                if not apk_path:
                    self.action_result.emit("install_apk", False, "未选择 APK 文件")
                    return
                if not os.path.isfile(apk_path):
                    self.action_result.emit("install_apk", False, f"APK 文件不存在: {apk_path}")
                    return
                if not self.device_id:
                    self.action_result.emit("install_apk", False, "安装 APK 前请先选择设备")
                    return

                result = self.controller.execute_adb_command(["install", "-r", apk_path], self.device_id)
                output = (result[1] or "").strip() or "(无输出)"
                if result[0]:
                    self.action_result.emit(
                        "install_apk",
                        True,
                        f"安装 APK 成功: {os.path.basename(apk_path)}\n{output}",
                    )
                else:
                    self.action_result.emit(
                        "install_apk",
                        False,
                        f"安装 APK 失败: {os.path.basename(apk_path)}\n{output}",
                    )
                return

            if self.action == "install_multiple_apk":
                apk_paths = self.extra if isinstance(self.extra, (list, tuple)) else []
                apk_paths = [str(path).strip().strip('"') for path in apk_paths if str(path).strip()]
                if not apk_paths:
                    self.action_result.emit("install_multiple_apk", False, "未选择 APK 文件")
                    return
                missing_files = [path for path in apk_paths if not os.path.isfile(path)]
                if missing_files:
                    self.action_result.emit(
                        "install_multiple_apk",
                        False,
                        "以下 APK 文件不存在:\n" + "\n".join(missing_files),
                    )
                    return
                if not self.device_id:
                    self.action_result.emit("install_multiple_apk", False, "安装分包前请先选择设备")
                    return

                result = self.controller.execute_adb_command(["install-multiple", "-r", *apk_paths], self.device_id)
                output = (result[1] or "").strip() or "(无输出)"
                joined_names = ", ".join(os.path.basename(path) for path in apk_paths)
                if result[0]:
                    self.action_result.emit(
                        "install_multiple_apk",
                        True,
                        f"安装分包成功({len(apk_paths)} 个): {joined_names}\n{output}",
                    )
                else:
                    self.action_result.emit(
                        "install_multiple_apk",
                        False,
                        f"安装分包失败({len(apk_paths)} 个): {joined_names}\n{output}",
                    )
                return

            if self.action == "adb_command":
                command_parts, explicit_device_id = self._normalize_adb_command(self.extra)
                if not command_parts:
                    self.action_result.emit("adb_command", False, "ADB 命令不能为空")
                    return

                target_device_id = self._resolve_device_for_command(command_parts, explicit_device_id)
                if target_device_id is None and not explicit_device_id:
                    if not command_parts[0].startswith("-") and command_parts[0] not in self.GLOBAL_COMMANDS and not self.device_id:
                        self.action_result.emit("adb_command", False, "当前命令需要先选择设备")
                        return

                result = self.controller.execute_adb_command(command_parts, target_device_id)
                output = (result[1] or "").strip() or "(无输出)"
                shown_adb_name = os.path.basename(getattr(self.controller, "adb_path", "adb") or "adb")
                prefix = f"$ {shown_adb_name}"
                if target_device_id:
                    prefix += f" -s {target_device_id}"
                prefix += f" {' '.join(command_parts)}"
                self.action_result.emit("adb_command", bool(result[0]), f"{prefix}\n{output}")
                return

            self.action_result.emit(self.action, False, f"不支持的设备动作: {self.action}")
        except Exception as e:
            self.action_result.emit(self.action, False, f"设备动作执行错误: {e}")


class AppManagerDialog(QDialog):
    """应用管理器对话框"""
    def __init__(self, parent, controller, initial_device_id=None):
        super().__init__(parent)
        self.controller = controller
        self.device_service = DeviceService(controller)
        self.initial_device_id = initial_device_id
        self.selected_device = None
        self.selected_package = None
        self.app_icons = {}  # 保存应用图标缓存
        self.app_list = []  # 保存应用列表
        self.state_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build", "app_manager_state.json")
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        self.recent_packages = self._load_recent_packages()  # 保存最近操作/访问的应用
        self.auto_open_export_dir = self._load_auto_open_export_dir()
        self.adb_command_history = self._load_adb_history()
        self.current_foreground_package = None
        
        self.setWindowTitle("应用管理器")
        self.resize(800, 600)
        
        self.setup_ui()
        
        # 刷新设备列表
        self.refresh_devices()

    def _load_recent_packages(self):
        """加载最近访问/操作的应用记录。"""
        state = load_settings(self.state_path, default={})
        recent = state.get("recent_packages", [])
        return [item for item in recent if isinstance(item, str)][:20]

    def _save_recent_packages(self):
        """保存最近访问/操作的应用记录。"""
        save_settings({
            "recent_packages": self.recent_packages[:20],
            "auto_open_export_dir": bool(getattr(self, 'auto_open_export_dir_cb', None).isChecked()) if hasattr(self, 'auto_open_export_dir_cb') else self.auto_open_export_dir,
            "adb_history": self.adb_command_history[:30],
        }, self.state_path)

    def _load_auto_open_export_dir(self):
        """加载导出 APK 后自动打开目录配置。"""
        state = load_settings(self.state_path, default={})
        return bool(state.get("auto_open_export_dir", False))

    def _load_adb_history(self):
        """加载 ADB 命令历史。"""
        state = load_settings(self.state_path, default={})
        history = state.get("adb_history", [])
        return [item for item in history if isinstance(item, str) and item.strip()][:30]
        
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

        filter_layout.addWidget(QLabel("过滤:"))
        self.filter_type_combo = QComboBox()
        self.filter_type_combo.addItems(["全部", "仅用户应用", "仅系统应用", "最近操作"])
        self.filter_type_combo.currentIndexChanged.connect(self.filter_apps)
        filter_layout.addWidget(self.filter_type_combo)

        self.recent_filter_btn = QPushButton("最近")
        self.recent_filter_btn.clicked.connect(self._show_recent_packages)
        filter_layout.addWidget(self.recent_filter_btn)

        self.foreground_filter_btn = QPushButton("前台定位")
        self.foreground_filter_btn.clicked.connect(self.show_foreground_app)
        filter_layout.addWidget(self.foreground_filter_btn)

        self.load_icons_cb = QCheckBox("加载图标")
        self.load_icons_cb.setChecked(True)
        self.load_icons_cb.stateChanged.connect(self.reload_apps)
        filter_layout.addWidget(self.load_icons_cb)

        sort_label = QLabel("排序:")
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["名称", "包名"])
        self.sort_combo.currentIndexChanged.connect(self.reload_apps)
        filter_layout.addWidget(sort_label)
        filter_layout.addWidget(self.sort_combo)
        
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

        extra_action_layout = QHBoxLayout()
        self.clear_data_btn = QPushButton("清除数据")
        self.clear_data_btn.clicked.connect(lambda: self.perform_app_action("clear_data"))
        self.clear_data_btn.setEnabled(False)
        extra_action_layout.addWidget(self.clear_data_btn)

        self.clear_cache_btn = QPushButton("清缓存")
        self.clear_cache_btn.clicked.connect(lambda: self.perform_app_action("clear_cache"))
        self.clear_cache_btn.setEnabled(False)
        extra_action_layout.addWidget(self.clear_cache_btn)

        self.export_apk_btn = QPushButton("导出APK")
        self.export_apk_btn.clicked.connect(lambda: self.perform_app_action("export_apk"))
        self.export_apk_btn.setEnabled(False)
        extra_action_layout.addWidget(self.export_apk_btn)

        self.install_apk_btn = QPushButton("安装APK")
        self.install_apk_btn.clicked.connect(self.install_apk_for_device)
        self.install_apk_btn.setEnabled(False)
        extra_action_layout.addWidget(self.install_apk_btn)

        self.auto_open_export_dir_cb = QCheckBox("导出后打开目录")
        self.auto_open_export_dir_cb.setChecked(self.auto_open_export_dir)
        extra_action_layout.addWidget(self.auto_open_export_dir_cb)

        self.foreground_btn = QPushButton("前台应用")
        self.foreground_btn.clicked.connect(self.show_foreground_app)
        extra_action_layout.addWidget(self.foreground_btn)

        app_list_layout.addLayout(extra_action_layout)
        
        # 应用详情区域
        app_detail_group = QGroupBox("应用详情")
        app_detail_layout = QVBoxLayout(app_detail_group)
        
        # 使用选项卡组织详情内容
        self.detail_tabs = QTabWidget()
        
        # 基本信息选项卡
        basic_info_tab = QWidget()
        basic_info_layout = QGridLayout(basic_info_tab)
        self.detail_value_labels = {}
        detail_fields = [
            ("应用名称", "name"),
            ("包名", "package"),
            ("设备", "device"),
            ("应用类型", "app_type"),
            ("是否前台", "is_foreground"),
            ("是否最近使用", "is_recent"),
            ("安装路径", "path"),
            ("版本名", "version_name"),
            ("版本号", "version_code"),
            ("UID", "uid"),
        ]
        for row, (label_text, key) in enumerate(detail_fields):
            label = QLabel(f"{label_text}:")
            value = QLabel("-")
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            value.setWordWrap(True)
            basic_info_layout.addWidget(label, row, 0)
            basic_info_layout.addWidget(value, row, 1)
            self.detail_value_labels[key] = value
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

        self.adb_tab = QWidget()
        adb_layout = QVBoxLayout(self.adb_tab)

        adb_path_label = QLabel(f"ADB 路径: {getattr(self.controller, 'adb_path', 'adb')}")
        adb_path_label.setWordWrap(True)
        adb_path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        adb_layout.addWidget(adb_path_label)

        adb_hint_label = QLabel(
            "输入 ADB 子命令即可执行，例如：shell pm list packages -3、shell getprop ro.product.model。"
            "\n无需输入 adb；普通设备命令会自动附加当前选中的设备，install/connect/devices 等也支持直接执行。"
        )
        adb_hint_label.setWordWrap(True)
        adb_layout.addWidget(adb_hint_label)

        adb_input_layout = QHBoxLayout()
        self.adb_command_input = QLineEdit()
        self.adb_command_input.setPlaceholderText("例如: shell pm list packages -3，可使用 {pkg} / {device} 占位符")
        self.adb_command_input.returnPressed.connect(self.execute_custom_adb_command)
        adb_input_layout.addWidget(self.adb_command_input, 1)

        self.execute_adb_btn = QPushButton("执行 ADB")
        self.execute_adb_btn.clicked.connect(self.execute_custom_adb_command)
        adb_input_layout.addWidget(self.execute_adb_btn)
        adb_layout.addLayout(adb_input_layout)

        adb_history_layout = QHBoxLayout()
        adb_history_layout.addWidget(QLabel("历史命令:"))
        self.adb_history_combo = QComboBox()
        self.adb_history_combo.setMinimumWidth(260)
        self._refresh_adb_history_combo()
        self.adb_history_combo.currentIndexChanged.connect(self._use_selected_adb_history)
        adb_history_layout.addWidget(self.adb_history_combo, 1)

        self.fill_history_btn = QPushButton("填入")
        self.fill_history_btn.clicked.connect(self._use_selected_adb_history)
        adb_history_layout.addWidget(self.fill_history_btn)
        adb_layout.addLayout(adb_history_layout)

        quick_command_layout = QHBoxLayout()
        quick_command_layout.addWidget(QLabel("常用命令:"))
        self.quick_command_combo = QComboBox()
        self.quick_command_combo.addItem("设备型号", "shell getprop ro.product.model")
        self.quick_command_combo.addItem("应用路径", "shell pm path {pkg}")
        self.quick_command_combo.addItem("应用详情", "shell dumpsys package {pkg}")
        self.quick_command_combo.addItem("打开应用设置页", "shell am start -a android.settings.APPLICATION_DETAILS_SETTINGS -d package:{pkg}")
        self.quick_command_combo.addItem("强制停止当前应用", "shell am force-stop {pkg}")
        self.quick_command_combo.addItem("启动当前应用", "shell monkey -p {pkg} -c android.intent.category.LAUNCHER 1")
        self.quick_command_combo.addItem("查看用户应用列表", "shell pm list packages -3")
        self.quick_command_combo.addItem("查看前台页面栈", "shell dumpsys activity activities")
        quick_command_layout.addWidget(self.quick_command_combo, 1)

        self.fill_quick_command_btn = QPushButton("填入常用命令")
        self.fill_quick_command_btn.clicked.connect(self._fill_quick_adb_command)
        quick_command_layout.addWidget(self.fill_quick_command_btn)

        self.run_quick_command_btn = QPushButton("执行常用命令")
        self.run_quick_command_btn.clicked.connect(self._run_quick_adb_command)
        quick_command_layout.addWidget(self.run_quick_command_btn)
        adb_layout.addLayout(quick_command_layout)

        adb_action_layout = QHBoxLayout()
        self.install_apk_tab_btn = QPushButton("安装APK")
        self.install_apk_tab_btn.clicked.connect(self.install_apk_for_device)
        self.install_apk_tab_btn.setEnabled(False)
        adb_action_layout.addWidget(self.install_apk_tab_btn)

        self.install_split_apk_tab_btn = QPushButton("安装分包")
        self.install_split_apk_tab_btn.clicked.connect(self.install_split_apk_for_device)
        self.install_split_apk_tab_btn.setEnabled(False)
        adb_action_layout.addWidget(self.install_split_apk_tab_btn)

        self.clear_adb_output_btn = QPushButton("清空输出")
        self.clear_adb_output_btn.clicked.connect(lambda: self.adb_output_text.clear())
        adb_action_layout.addWidget(self.clear_adb_output_btn)
        adb_action_layout.addStretch(1)
        adb_layout.addLayout(adb_action_layout)

        self.adb_output_text = QTextEdit()
        self.adb_output_text.setReadOnly(True)
        adb_layout.addWidget(self.adb_output_text)

        self.detail_tabs.addTab(self.adb_tab, "ADB 命令")
        
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
        self._clear_detail_summary()
        
        # 禁用操作按钮
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.uninstall_btn.setEnabled(False)
        self.info_btn.setEnabled(False)
        self.clear_data_btn.setEnabled(False)
        self.clear_cache_btn.setEnabled(False)
        self.export_apk_btn.setEnabled(False)
        self._update_device_action_controls()
        
        try:
            devices, selected_device = self.device_service.sync_device_widgets(
                self.device_combo,
                preferred_device_id=self.initial_device_id,
            )

            if not devices:
                self.log("未检测到设备")
                return
            self.selected_device = selected_device
            self._update_device_action_controls()
                
        except Exception as e:
            self.log(f"刷新设备列表出错: {e}")
            
    def on_device_changed(self, index):
        """设备选择改变处理"""
        self.app_list_widget.clear()
        self._clear_detail_summary()
        
        if index >= 0:
            self.selected_device = self.device_combo.currentData()
            self.log(f"已选择设备: {self.selected_device}")
            self._update_device_action_controls()
            
            # 加载应用列表
            self.load_app_list()
        else:
            self.selected_device = None
            self._update_device_action_controls()
            
    def get_current_device(self):
        """获取当前选择的设备ID"""
        if self.device_combo.currentIndex() >= 0:
            return self.device_combo.currentData()
        return None

    def _update_device_action_controls(self):
        """更新设备级操作控件状态。"""
        has_device = bool(self.get_current_device())
        if hasattr(self, 'install_apk_btn'):
            self.install_apk_btn.setEnabled(has_device)
        if hasattr(self, 'install_apk_tab_btn'):
            self.install_apk_tab_btn.setEnabled(has_device)
        if hasattr(self, 'install_split_apk_tab_btn'):
            self.install_split_apk_tab_btn.setEnabled(has_device)

    def _set_device_action_running(self, running):
        """在设备级动作执行期间锁定相关控件。"""
        if hasattr(self, 'adb_command_input'):
            self.adb_command_input.setEnabled(not running)
        if hasattr(self, 'execute_adb_btn'):
            self.execute_adb_btn.setEnabled(not running)
        if hasattr(self, 'clear_adb_output_btn'):
            self.clear_adb_output_btn.setEnabled(not running)
        if hasattr(self, 'fill_history_btn'):
            self.fill_history_btn.setEnabled(not running)
        if hasattr(self, 'adb_history_combo'):
            self.adb_history_combo.setEnabled(not running)
        if hasattr(self, 'quick_command_combo'):
            self.quick_command_combo.setEnabled(not running)
        if hasattr(self, 'fill_quick_command_btn'):
            self.fill_quick_command_btn.setEnabled(not running)
        if hasattr(self, 'run_quick_command_btn'):
            self.run_quick_command_btn.setEnabled(not running)

        if running:
            if hasattr(self, 'install_apk_btn'):
                self.install_apk_btn.setEnabled(False)
            if hasattr(self, 'install_apk_tab_btn'):
                self.install_apk_tab_btn.setEnabled(False)
            if hasattr(self, 'install_split_apk_tab_btn'):
                self.install_split_apk_tab_btn.setEnabled(False)
            return

        self._update_device_action_controls()

    def _refresh_adb_history_combo(self):
        """刷新 ADB 历史命令下拉框。"""
        if not hasattr(self, 'adb_history_combo'):
            return
        current_text = self.adb_history_combo.currentText() if self.adb_history_combo.count() else ""
        self.adb_history_combo.blockSignals(True)
        self.adb_history_combo.clear()
        self.adb_history_combo.addItem("选择历史命令...")
        for item in self.adb_command_history:
            self.adb_history_combo.addItem(item)
        if current_text:
            index = self.adb_history_combo.findText(current_text)
            if index >= 0:
                self.adb_history_combo.setCurrentIndex(index)
            else:
                self.adb_history_combo.setCurrentIndex(0)
        else:
            self.adb_history_combo.setCurrentIndex(0)
        self.adb_history_combo.blockSignals(False)

    def _remember_adb_command(self, command_text):
        """记录最近执行过的 ADB 命令。"""
        normalized = (command_text or "").strip()
        if not normalized:
            return
        if normalized in self.adb_command_history:
            self.adb_command_history.remove(normalized)
        self.adb_command_history.insert(0, normalized)
        self.adb_command_history = self.adb_command_history[:30]
        self._refresh_adb_history_combo()
        self._save_recent_packages()

    def _use_selected_adb_history(self):
        """将历史命令填入输入框。"""
        if not hasattr(self, 'adb_history_combo'):
            return
        command_text = self.adb_history_combo.currentText().strip()
        if not command_text or command_text == "选择历史命令...":
            return
        self.adb_command_input.setText(command_text)

    def _fill_quick_adb_command(self):
        """把常用命令模板填入输入框。"""
        command_text = str(self.quick_command_combo.currentData() or "").strip()
        if command_text:
            self.adb_command_input.setText(command_text)

    def _run_quick_adb_command(self):
        """直接执行当前选择的常用命令。"""
        self._fill_quick_adb_command()
        self.execute_custom_adb_command()

    def _resolve_adb_command_placeholders(self, command_text):
        """解析 {pkg} / {device} 之类的输入占位符。"""
        resolved = command_text
        if "{pkg}" in resolved:
            if not self.selected_package:
                return None, "当前命令包含 {pkg}，请先在左侧选择一个应用"
            resolved = resolved.replace("{pkg}", self.selected_package)
        if "{device}" in resolved:
            current_device = self.get_current_device()
            if not current_device:
                return None, "当前命令包含 {device}，请先选择设备"
            resolved = resolved.replace("{device}", current_device)
        return resolved, None

    def _append_adb_output(self, text):
        """向 ADB 输出面板追加内容。"""
        import datetime

        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.adb_output_text.append(f"[{timestamp}]")
        self.adb_output_text.append(text)
        self.adb_output_text.append("")
        scrollbar = self.adb_output_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _start_device_action(self, action, extra=None):
        """启动设备级后台任务。"""
        self._set_device_action_running(True)
        self.device_action_thread = DeviceActionThread(
            self.controller,
            self.get_current_device(),
            action,
            extra=extra,
        )
        self.device_action_thread.action_result.connect(self.handle_device_action_result)
        self.device_action_thread.start()

    def install_apk_for_device(self):
        """为当前设备安装 APK。"""
        device_id = self.get_current_device()
        if not device_id:
            self.log("安装 APK 前请先选择设备")
            return

        filename, _ = QFileDialog.getOpenFileName(self, "选择 APK 文件", "", "APK 文件 (*.apk);;所有文件 (*)")
        if not filename:
            return

        self.detail_tabs.setCurrentWidget(self.adb_tab)
        self.log(f"准备安装 APK: {filename}")
        self._append_adb_output(f"准备安装 APK 到设备 {device_id}:\n{filename}")
        self._start_device_action("install_apk", extra=filename)

    def install_split_apk_for_device(self):
        """为当前设备安装多 APK 分包。"""
        device_id = self.get_current_device()
        if not device_id:
            self.log("安装分包前请先选择设备")
            return

        filenames, _ = QFileDialog.getOpenFileNames(self, "选择多个 APK 文件", "", "APK 文件 (*.apk);;所有文件 (*)")
        if not filenames:
            return

        self.detail_tabs.setCurrentWidget(self.adb_tab)
        self.log(f"准备安装分包，共 {len(filenames)} 个 APK")
        self._append_adb_output(
            f"准备安装分包到设备 {device_id} (共 {len(filenames)} 个):\n" + "\n".join(filenames)
        )
        self._start_device_action("install_multiple_apk", extra=filenames)

    def execute_custom_adb_command(self):
        """执行用户输入的 ADB 子命令。"""
        raw_command_text = self.adb_command_input.text().strip()
        if not raw_command_text:
            self.log("请输入要执行的 ADB 子命令")
            return

        command_text, error = self._resolve_adb_command_placeholders(raw_command_text)
        if error:
            self.log(error)
            return

        self.detail_tabs.setCurrentWidget(self.adb_tab)
        self._remember_adb_command(raw_command_text)
        self.log(f"正在执行 ADB 命令: {command_text}")
        self._start_device_action("adb_command", extra=command_text)

    def handle_device_action_result(self, action, success, output):
        """处理设备级动作结果。"""
        self._set_device_action_running(False)
        self._append_adb_output(output)

        if action in {"install_apk", "install_multiple_apk"}:
            self.log(output.splitlines()[0] if output else "APK 安装完成")
            if success and self.selected_device:
                QTimer.singleShot(1200, self.reload_apps)
            return

        if action == "adb_command":
            self.log("ADB 命令执行成功" if success else "ADB 命令执行失败")
            return

        self.log(output)
            
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
        self._clear_detail_summary()
        
        # 显示进度条
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        
        # 在后台线程中加载
        prefetch = 12 if self.load_icons_cb.isChecked() else 0
        sort_by_name = (self.sort_combo.currentIndex() == 0)
        self.app_list_thread = AppListThread(
            self.controller, 
            device_id,
            True,
            self.load_icons_cb.isChecked(),
            prefetch,
            sort_by_name
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
            console_log(f"更新应用图标出错: {e}", "ERROR")
        
    def update_app_list(self, app_list):
        """更新应用列表"""
        self.app_list = app_list
        self.app_list_widget.clear()
        
        if not app_list:
            self.log("没有找到应用")
            self.progress_bar.setVisible(False)
            return
        
        # 添加应用到列表
        for app in app_list:
            display_name = app["display_name"]
            package_name = app["package_name"]
            item = QListWidgetItem(f"{display_name} ({package_name})")
            item.setData(Qt.UserRole, package_name)
            item.setData(Qt.UserRole + 1, app)
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
        self.filter_apps()
        
    def reload_apps(self):
        """重新加载应用列表"""
        self.load_app_list()
        
    def filter_apps(self):
        """根据输入过滤应用列表"""
        filter_text = self.filter_input.text().lower()
        filter_type = self.filter_type_combo.currentText() if hasattr(self, 'filter_type_combo') else "全部"
        recent_set = set(self.recent_packages)
        for i in range(self.app_list_widget.count()):
            item = self.app_list_widget.item(i)
            package_name = item.data(Qt.UserRole).lower()
            metadata = item.data(Qt.UserRole + 1) or {}

            search_candidates = [
                item.text().lower(),
                package_name,
                str(metadata.get("search_name", "")).lower(),
                str(metadata.get("search_pinyin", "")).lower(),
                str(metadata.get("search_initials", "")).lower(),
            ]
            match_text = (not filter_text) or any(filter_text in candidate for candidate in search_candidates if candidate)

            if filter_type == "仅用户应用":
                match_type = not bool(metadata.get("is_system", False))
            elif filter_type == "仅系统应用":
                match_type = bool(metadata.get("is_system", False))
            elif filter_type == "最近操作":
                match_type = package_name in recent_set
            else:
                match_type = True

            item.setHidden(not (match_text and match_type))
            
    def on_app_selected(self):
        """应用选择改变处理"""
        current_item = self.app_list_widget.currentItem()
        if current_item:
            self.selected_package = current_item.data(Qt.UserRole)
            detail_data = self._build_selected_app_summary(current_item)
            self._apply_detail_summary(detail_data)
            self._mark_recent_package(self.selected_package)
            self.detail_tabs.setCurrentIndex(0)
            
            # 启用操作按钮
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(True)
            self.uninstall_btn.setEnabled(True)
            self.info_btn.setEnabled(True)
            self.clear_data_btn.setEnabled(True)
            self.clear_cache_btn.setEnabled(True)
            self.export_apk_btn.setEnabled(True)
        else:
            self.selected_package = None
            self._clear_detail_summary()
            
            # 禁用操作按钮
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
            self.uninstall_btn.setEnabled(False)
            self.info_btn.setEnabled(False)
            self.clear_data_btn.setEnabled(False)
            self.clear_cache_btn.setEnabled(False)
            self.export_apk_btn.setEnabled(False)
        
    def perform_app_action(self, action):
        """执行应用操作"""
        if not self.selected_device or not self.selected_package:
            self.log("请先选择设备和应用")
            return
            
        extra = None

        # 确认高风险操作
        if action == "uninstall":
            reply = self.ask_confirmation(
                "确认卸载",
                f"确定要卸载应用 {self.selected_package} 吗？\n此操作不可恢复！",
                default=QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
        elif action == "clear_data":
            reply = self.ask_confirmation(
                "确认清除数据",
                f"确定要清除应用 {self.selected_package} 的数据吗？\n此操作会移除登录状态和本地数据。",
                default=QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
        elif action == "clear_cache":
            reply = self.ask_confirmation(
                "确认清除缓存",
                f"确定要尝试清除应用 {self.selected_package} 的缓存吗？",
                default=QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
        elif action == "export_apk":
            safe_name = self.selected_package.split('.')[-1]
            filename, _ = QFileDialog.getSaveFileName(self, "导出 APK", f"{safe_name}.apk", "APK 文件 (*.apk)")
            if not filename:
                return
            extra = filename
                
        # 显示操作信息
        action_descriptions = {
            "start": "启动",
            "stop": "停止",
            "uninstall": "卸载",
            "clear_data": "清除数据",
            "clear_cache": "清除缓存",
            "export_apk": "导出APK",
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
            action,
            extra=extra,
        )
        self.action_thread.action_result.connect(self.handle_action_result)
        self.action_thread.start()
        
    def handle_action_result(self, success, output):
        """处理操作结果"""
        self.log(output)
        if success and self.selected_package:
            self._mark_recent_package(self.selected_package)
        
        # 如果是卸载操作且成功，则从列表中移除
        if success and self.selected_package and output.startswith("已卸载应用"):
            for i in range(self.app_list_widget.count()):
                item = self.app_list_widget.item(i)
                if item.data(Qt.UserRole) == self.selected_package:
                    self.app_list_widget.takeItem(i)
                    break
            self._clear_detail_summary()
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
            self.clear_data_btn.setEnabled(True)
            self.clear_cache_btn.setEnabled(True)
            self.export_apk_btn.setEnabled(True)

        if success and output.startswith("已导出APK到:") and self.auto_open_export_dir_cb.isChecked():
            export_path = output.split("已导出APK到:", 1)[1].strip()
            export_dir = os.path.dirname(export_path)
            if export_dir and os.path.isdir(export_dir):
                if open_path(export_dir):
                    self.log(f"已打开APK导出目录: {export_dir}")
                else:
                    self.log(f"导出APK成功，但打开目录失败: {export_dir}")
            
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

    def show_foreground_app(self):
        """查看当前前台应用。"""
        device_id = self.get_current_device()
        if not device_id:
            self.log("请先选择一个设备")
            return

        result = self.controller.execute_adb_command("shell dumpsys activity activities", device_id)
        if not result[0] or not result[1]:
            self.log(f"获取前台应用失败: {result[1]}")
            return

        output = result[1]
        patterns = [
            r"mResumedActivity:.*?\s([A-Za-z0-9_.$]+)/([A-Za-z0-9_.$]+)",
            r"topResumedActivity=ActivityRecord\{.*?\s([A-Za-z0-9_.$]+)/([A-Za-z0-9_.$]+)",
            r"mFocusedApp=.*?\s([A-Za-z0-9_.$]+)/([A-Za-z0-9_.$]+)",
        ]
        package_name = None
        activity_name = None
        for pattern in patterns:
            match = re.search(pattern, output)
            if match:
                package_name, activity_name = match.group(1), match.group(2)
                break

        if package_name:
            self._mark_recent_package(package_name)
            self.current_foreground_package = package_name
            if hasattr(self, 'filter_type_combo'):
                self.filter_type_combo.setCurrentText("全部")
            if hasattr(self, 'filter_input'):
                self.filter_input.clear()
            self.filter_apps()
            self._select_package_in_list(package_name)
            self._refresh_selected_detail_summary()
            self.log(f"当前前台应用: {package_name}/{activity_name}")
            QMessageBox.information(self, "当前前台应用", f"包名: {package_name}\n页面: {activity_name}")
        else:
            self.log("未能识别当前前台应用")

    def _build_selected_app_summary(self, current_item):
        """构建当前选中应用的摘要信息。"""
        package_name = current_item.data(Qt.UserRole)
        metadata = current_item.data(Qt.UserRole + 1) or {}
        title = metadata.get("display_name") or current_item.text().split(" (", 1)[0]
        device_id = self.selected_device or "未知设备"

        summary = {
            "name": title,
            "package": package_name,
            "device": device_id,
            "app_type": "系统应用" if metadata.get("is_system", False) else "用户应用",
            "is_foreground": "是" if package_name == self.current_foreground_package else "否",
            "is_recent": "是" if package_name in self.recent_packages else "否",
            "path": "-",
            "version_name": "-",
            "version_code": "-",
            "uid": "-",
        }

        path_result = self.controller.execute_adb_command(f"shell pm path {package_name}", device_id)
        if path_result[0] and path_result[1]:
            for line in path_result[1].splitlines():
                if line.startswith("package:"):
                    summary["path"] = line.replace('package:', '').strip()
                    break

        info_result = self.controller.execute_adb_command(f"shell dumpsys package {package_name}", device_id)
        if info_result[0] and info_result[1]:
            content = info_result[1]
            version_name = re.search(r"versionName=([^\s]+)", content)
            version_code = re.search(r"versionCode=(\d+)", content)
            uid_match = re.search(r"userId=(\d+)", content)
            if version_name:
                summary["version_name"] = version_name.group(1)
            if version_code:
                summary["version_code"] = version_code.group(1)
            if uid_match:
                summary["uid"] = uid_match.group(1)

        return summary

    def _apply_detail_summary(self, detail_data):
        """把结构化应用信息显示到详情面板。"""
        for key, label in self.detail_value_labels.items():
            label.setText(str(detail_data.get(key, "-")))

    def _refresh_selected_detail_summary(self):
        """按当前选中项重新刷新结构化详情。"""
        current_item = self.app_list_widget.currentItem()
        if current_item:
            self._apply_detail_summary(self._build_selected_app_summary(current_item))

    def _clear_detail_summary(self):
        """清空结构化详情面板。"""
        for label in getattr(self, 'detail_value_labels', {}).values():
            label.setText("-")

    def _mark_recent_package(self, package_name):
        """记录最近访问/操作的应用。"""
        if not package_name:
            return
        if package_name in self.recent_packages:
            self.recent_packages.remove(package_name)
        self.recent_packages.insert(0, package_name)
        self.recent_packages = self.recent_packages[:20]
        self._save_recent_packages()
        self._refresh_selected_detail_summary()
        if hasattr(self, 'filter_type_combo') and self.filter_type_combo.currentText() == "最近操作":
            self.filter_apps()

    def _select_package_in_list(self, package_name):
        """在列表中定位并选中指定包名。"""
        for index in range(self.app_list_widget.count()):
            item = self.app_list_widget.item(index)
            if item.data(Qt.UserRole) == package_name:
                item.setHidden(False)
                self.app_list_widget.setCurrentItem(item)
                self.app_list_widget.scrollToItem(item)
                return True
        return False

    def _show_recent_packages(self):
        """快捷切换到最近使用过滤。"""
        self.filter_type_combo.setCurrentText("最近操作")
        self.filter_apps()

    def closeEvent(self, event):
        self._save_recent_packages()
        super().closeEvent(event)
            
    def log(self, message):
        """向日志中添加消息"""
        # 添加时间戳
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        
        # 滚动到底部
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def ask_confirmation(self, title, message, *, default=QMessageBox.No):
        """统一当前对话框内的确认提示。"""
        self.log(message.replace("\n", " "))
        return QMessageBox.question(self, title, message, QMessageBox.Yes | QMessageBox.No, default)


if __name__ == "__main__":
    # 独立运行时的代码
    app = QApplication(sys.argv)
    
    from scrcpy_controller import ScrcpyController
    controller = ScrcpyController()
    
    dialog = AppManagerDialog(None, controller)
    dialog.show()
    
    sys.exit(app.exec_()) 
