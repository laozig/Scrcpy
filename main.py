#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import sys
import os
import subprocess
import ctypes
from ctypes import wintypes
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QLabel,
    QComboBox, QPushButton, QLineEdit, QFileDialog, QMessageBox, QTextEdit,
    QAction, QCheckBox, QGroupBox, QGridLayout, QDialog
)
from PyQt5.QtCore import Qt, QProcess, QTimer
from PyQt5.QtGui import QFont, QPalette, QColor

from command_service import ScrcpyCommandService
from config_service import ConfigService
from device_service import DeviceService
from process_manager import ProcessManager
from screenshot_service import ScreenshotService
from scrcpy_controller import ScrcpyController
from runtime_helpers import (
    check_command_available,
    find_adb_path as resolve_adb_path,
    find_scrcpy_path as resolve_scrcpy_path,
)
from ui_support_service import UISupportService
from utils import console_log, decode_process_output, open_path
from wifi_service import WifiConnectionService

APP_VERSION = "v1.0"

class ScrcpyUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scrcpy_config.json")
        self.config_service = ConfigService(self.config_path)
        self.runtime_path_overrides = self.config_service.load_runtime_paths()
        self.adb_resolution = {}
        self.scrcpy_resolution = {}
        self.process = QProcess()
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.adb_path = self.find_adb_path()  # 自动查找ADB路径
        self.scrcpy_path = self.find_scrcpy_path()  # 自动查找scrcpy路径
        self.ui_support_service = UISupportService()
        
        # 设置应用图标
        self.set_application_icon()

        self.pending_selected_device = None
        self.last_connected_device = None
        self.device_status_map = {}
        self.device_profiles = {}
        self.device_window_titles = {}
        self.current_profile_device_id = None
        self.default_device_profile = {}
        self._suspend_ui_reactions = False
        self.screenshot_dir = ""
        self.record_outputs = {}

        self.process_manager = ProcessManager(self)
        self.device_processes = self.process_manager.device_processes
        self.control_bars = self.process_manager.control_bars
        self.process_tracking = self.process_manager.process_tracking
        
        # 添加应用程序退出事件处理
        QApplication.instance().aboutToQuit.connect(self.cleanup_processes)
        
        # 标记应用状态，防止在对象销毁后访问
        self.is_closing = False
        self._cleanup_done = False
        
        # 上次日志消息，用于避免重复
        self.last_log_message = ""
        self.repeat_count = 0
        self.log_entries = []
        
        # 创建控制器
        self.controller = ScrcpyController(adb_path=self.adb_path, scrcpy_path=self.scrcpy_path)
        self.device_service = DeviceService(self.controller)
        self.command_service = ScrcpyCommandService()
        self.wifi_service = WifiConnectionService(self, self.adb_path, self.process_manager)
        self.screenshot_service = ScreenshotService(self, self.controller)
        self.event_monitor = None  # 事件监控器
        
        # 计算界面缩放，先设置主题再应用尺寸缩放
        self.ui_scale = self.compute_ui_scale_v2()
        self.apply_dark_theme()
        self.apply_scale_styles()
        
        self.initUI()

        # 创建设备检查定时器
        self.device_timer = QTimer()
        self.device_timer.timeout.connect(self.check_devices)

        self.load_config()
        self.default_device_profile = self.config_service.collect_device_profile(self)
        
        # 检查ADB是否可用
        if not self.check_adb_available():
            self.show_warning_message(
                "警告",
                f"ADB路径({self.adb_path})不可用。请检查ADB是否已安装并在环境变量中。",
                show_dialog=True,
            )
        else:
            self.log(f"使用ADB路径: {self.adb_path}")
            
        # 检查scrcpy是否可用
        if not self.check_scrcpy_available():
            self.show_warning_message(
                "警告",
                f"scrcpy路径({self.scrcpy_path})不可用。请检查scrcpy是否已安装并在环境变量中。",
                show_dialog=True,
            )
        else:
            self.log(f"使用scrcpy路径: {self.scrcpy_path}")
        
        # 初始加载设备列表
        self.check_devices()

        self._log_runtime_dependency_status(show_dialog=False)

    def _track_process(self, process):
        """跟踪QProcess生命周期，避免对象过早释放。"""
        return self.process_manager.track_process(process)

    def _cleanup_tracked_process(self, process):
        """清理已结束的临时进程引用。"""
        self.process_manager.cleanup_tracked_process(process)

    def _build_single_device_command(self, device_id, window_title, window_x=100, window_y=100):
        """委托命令服务基于当前界面状态构建 scrcpy 命令。"""
        command, error, needs_warning = self.command_service.build_command_from_ui(
            self,
            self.scrcpy_path,
            device_id,
            window_title=window_title,
            window_x=window_x,
            window_y=window_y,
        )
        if error:
            if needs_warning:
                self.show_warning_message("警告", error, show_dialog=True)
            else:
                self.log(error)
            return None
        return command

    def _launch_device_process(self, device_id, command, success_message=None):
        """启动并跟踪单个设备的 scrcpy 进程。"""
        self.record_outputs[device_id] = self._extract_record_output_path(command)
        self.device_window_titles[device_id] = self._extract_window_title(command)
        process = self.process_manager.launch_device_process(device_id, command, success_message)
        self.last_connected_device = device_id
        self.pending_selected_device = device_id
        QTimer.singleShot(0, lambda: self.check_devices(False))
        QTimer.singleShot(1200, lambda dev=device_id: self._apply_running_window_topmost_for_device(dev, log_result=False))
        return process

    def _extract_window_title(self, command):
        """从 scrcpy 启动命令中提取窗口标题。"""
        try:
            if "--window-title" in command:
                index = command.index("--window-title")
                if index + 1 < len(command):
                    return command[index + 1]
        except ValueError:
            pass
        return ""

    def _find_visible_windows_by_pid(self, pid):
        """在 Windows 上根据进程 PID 查找可见顶层窗口句柄。"""
        if os.name != "nt" or not pid:
            return []

        user32 = ctypes.windll.user32
        handles = []
        enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def callback(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            if user32.GetWindowTextLengthW(hwnd) <= 0:
                return True

            window_pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
            if int(window_pid.value) == int(pid):
                handles.append(hwnd)
            return True

        user32.EnumWindows(enum_proc(callback), 0)
        return handles

    def _find_visible_windows_by_title(self, title_text):
        """在 Windows 上根据窗口标题模糊匹配可见顶层窗口。"""
        if os.name != "nt" or not title_text:
            return []

        user32 = ctypes.windll.user32
        handles = []
        enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def callback(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True

            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            current_title = buffer.value or ""
            if title_text in current_title:
                handles.append(hwnd)
            return True

        user32.EnumWindows(enum_proc(callback), 0)
        return handles

    def _set_window_topmost(self, hwnd, enabled):
        """设置指定窗口是否置顶。"""
        if os.name != "nt" or not hwnd:
            return False

        user32 = ctypes.windll.user32
        user32.SetWindowPos.argtypes = [
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint,
        ]
        user32.SetWindowPos.restype = wintypes.BOOL
        insert_after = wintypes.HWND(-1 if enabled else -2)  # HWND_TOPMOST / HWND_NOTOPMOST
        flags = 0x0001 | 0x0002 | 0x0010 | 0x0040  # SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE | SWP_SHOWWINDOW
        try:
            return bool(user32.SetWindowPos(hwnd, insert_after, 0, 0, 0, 0, flags))
        except Exception:
            return False

    def _apply_running_window_topmost_for_device(self, device_id, *, enabled=None, log_result=True):
        """把当前 UI 的置顶状态应用到指定运行中的 scrcpy 窗口。"""
        if os.name != "nt":
            return False

        process = self.device_processes.get(device_id)
        if not process or process.state() != QProcess.Running:
            return False

        pid = int(process.processId()) if process.processId() else 0
        if not pid:
            return False

        target_state = self.always_top_cb.isChecked() if enabled is None else bool(enabled)
        handles = self._find_visible_windows_by_pid(pid)
        if not handles:
            handles = self._find_visible_windows_by_title(self.device_window_titles.get(device_id, ""))
        applied_count = 0
        for hwnd in handles:
            if self._set_window_topmost(hwnd, target_state):
                applied_count += 1

        if applied_count and log_result:
            action_text = "已置顶" if target_state else "已取消置顶"
            self.log(f"设备 {device_id} 窗口{action_text}")
        elif log_result and self.device_window_titles.get(device_id):
            self.log(f"未找到设备 {device_id} 的窗口，暂未能即时更新置顶状态")
        return applied_count > 0

    def _apply_running_windows_topmost(self, *, enabled=None, log_result=True):
        """把置顶选项即时应用到所有运行中的 scrcpy 窗口。"""
        changed = False
        for device_id, process in list(self.device_processes.items()):
            if process and process.state() == QProcess.Running:
                changed = self._apply_running_window_topmost_for_device(device_id, enabled=enabled, log_result=log_result) or changed
        return changed

    def _handle_always_on_top_changed(self, _state):
        """运行中切换“窗口置顶”时，立即同步到已打开的 scrcpy 窗口。"""
        enabled = self.always_top_cb.isChecked()
        if not self._apply_running_windows_topmost(enabled=enabled, log_result=True):
            if self._get_running_device_ids():
                QTimer.singleShot(900, lambda state=enabled: self._apply_running_windows_topmost(enabled=state, log_result=True))

    def _extract_record_output_path(self, command):
        """从 scrcpy 启动命令中提取录屏输出路径。"""
        try:
            if "--record" in command:
                index = command.index("--record")
                if index + 1 < len(command):
                    return command[index + 1]
        except ValueError:
            pass
        return None

    def _handle_recording_finished(self, device_id, record_path):
        """录屏进程结束后按配置打开目录或文件。"""
        if not record_path or not os.path.exists(record_path):
            return

        self.log(f"录屏文件已保存: {record_path}")
        self.statusBar().showMessage(f"录屏已保存: {record_path}", 3000)

        open_file = hasattr(self, 'open_record_file_action') and self.open_record_file_action.isChecked()
        open_dir = hasattr(self, 'open_record_dir_action') and self.open_record_dir_action.isChecked()
        if not open_file and not open_dir:
            return

        if open_file:
            if open_path(record_path):
                self.log(f"录屏完成，已打开文件: {record_path}")
            else:
                self.log(f"录屏完成，但打开文件失败: {record_path}")
        elif open_dir:
            record_dir = os.path.dirname(record_path)
            if open_path(record_dir):
                self.log(f"录屏完成，已打开目录: {record_dir}")
            else:
                self.log(f"录屏完成，但打开目录失败: {record_dir}")


    def _get_running_device_ids(self):
        return [
            device_id for device_id, process in self.device_processes.items()
            if process and process.state() == QProcess.Running
        ]

    def _run_cli_capture(self, command):
        """执行命令并返回输出文本。"""
        try:
            kwargs = {
                "capture_output": True,
                "text": True,
                "check": False,
            }
            if os.name == "nt":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            result = subprocess.run(command, **kwargs)
            output = (result.stdout or "").strip()
            error = (result.stderr or "").strip()
            return result.returncode == 0, output or error or "(无输出)"
        except Exception as e:
            return False, str(e)

    def collect_environment_health(self):
        """收集启动环境自检信息。"""
        dependencies = self.controller.check_dependencies()
        device_entries = self.controller.get_device_statuses()
        available_devices = [item for item in device_entries if item.get("status") == "device"]
        wireless_devices = [item for item in available_devices if item.get("transport") == "wifi"]
        offline_devices = [item for item in device_entries if item.get("status") == "offline"]
        unauthorized_devices = [item for item in device_entries if item.get("status") == "unauthorized"]
        return {
            "adb_available": bool(dependencies.get("adb")),
            "adb_version": dependencies.get("adb_version") or "未知",
            "adb_path": self.adb_path,
            "adb_source": (self.adb_resolution or {}).get("source", "unknown"),
            "scrcpy_available": bool(dependencies.get("scrcpy")),
            "scrcpy_version": dependencies.get("scrcpy_version") or "未知",
            "scrcpy_path": self.scrcpy_path,
            "scrcpy_source": (self.scrcpy_resolution or {}).get("source", "unknown"),
            "scrcpy_server_path": (self.scrcpy_resolution or {}).get("server_path") or os.environ.get("SCRCPY_SERVER_PATH", ""),
            "scrcpy_server_source": (self.scrcpy_resolution or {}).get("server_source") or "unknown",
            "app_version": APP_VERSION,
            "device_count": len(available_devices),
            "wireless_count": len(wireless_devices),
            "offline_count": len(offline_devices),
            "unauthorized_count": len(unauthorized_devices),
            "device_entries": device_entries,
        }

    def build_diagnosis_suggestions(self, health=None):
        """根据当前诊断状态生成简单修复建议。"""
        health = health or self.collect_environment_health()
        suggestions = []

        if not health.get("adb_available"):
            suggestions.append("ADB 不可用：请确认 platform-tools 已安装，并检查 ADB 路径或环境变量配置。")

        if not health.get("scrcpy_available"):
            suggestions.append("scrcpy 不可用：请确认 scrcpy 已安装，并检查 scrcpy 路径或环境变量配置。")

        if health.get("unauthorized_count", 0) > 0:
            suggestions.append("检测到未授权设备：请在手机上确认 USB 调试授权，并重新插拔数据线或重新执行 adb devices。")

        if health.get("offline_count", 0) > 0:
            suggestions.append("检测到离线设备：请检查 USB/WiFi 连接状态，可尝试重新连接设备或执行 adb disconnect 后重连。")

        if health.get("device_count", 0) == 0 and health.get("adb_available"):
            suggestions.append("当前没有可用设备：请确认手机已开启开发者选项与 USB 调试，或检查无线连接是否成功。")

        if health.get("wireless_count", 0) == 0 and health.get("device_count", 0) > 0:
            suggestions.append("当前没有无线设备：如果需要 WiFi 投屏，请先通过 USB 执行 TCP/IP 模式并使用无线连接功能。")

        if not suggestions:
            suggestions.append("未发现明显异常：当前环境整体正常，如仍有问题，可复制诊断结果继续排查。")

        return suggestions

    def show_startup_health_panel(self):
        """显示启动环境自检面板。"""
        if getattr(self, "_startup_health_panel", None) is not None:
            try:
                self._startup_health_panel.raise_()
                self._startup_health_panel.activateWindow()
                return
            except Exception:
                self._startup_health_panel = None

        health = self.collect_environment_health()
        dialog = QDialog(self)
        dialog.setWindowTitle("环境自检")
        dialog.setMinimumWidth(440)
        layout = QVBoxLayout(dialog)

        title = QLabel("启动环境自检")
        title.setStyleSheet("font-weight: 700; color: #2a7a6c; font-size: 14px;")
        layout.addWidget(title)

        grid = QGridLayout()
        rows = [
            ("ADB 是否可用", "是" if health["adb_available"] else "否"),
            ("ADB 版本", health["adb_version"]),
            ("scrcpy 是否可用", "是" if health["scrcpy_available"] else "否"),
            ("scrcpy 版本", health["scrcpy_version"]),
            ("当前版本", health["app_version"]),
            ("可用设备数", str(health["device_count"])),
            ("无线设备数", str(health["wireless_count"])),
            ("离线设备数", str(health["offline_count"])),
            ("未授权设备数", str(health["unauthorized_count"])),
        ]
        for row, (label_text, value_text) in enumerate(rows):
            grid.addWidget(QLabel(f"{label_text}:"), row, 0)
            value = QLabel(value_text)
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            if value_text in ("否",):
                value.setStyleSheet("color: #c85b52; font-weight: 600;")
            elif value_text in ("是",):
                value.setStyleSheet("color: #2a7a6c; font-weight: 600;")
            grid.addWidget(value, row, 1)
        layout.addLayout(grid)

        if health["device_entries"]:
            device_summary = QTextEdit()
            device_summary.setReadOnly(True)
            device_summary.setMaximumHeight(110)
            lines = [
                f"- {item.get('model', '未知设备')} ({item.get('device_id')}) [{item.get('status')}]"
                for item in health["device_entries"]
            ]
            device_summary.setPlainText("\n".join(lines))
            layout.addWidget(QLabel("设备摘要:"))
            layout.addWidget(device_summary)

        suggestion_text = QTextEdit()
        suggestion_text.setReadOnly(True)
        suggestion_text.setMaximumHeight(96)
        suggestion_text.setPlainText("\n".join(f"- {item}" for item in self.build_diagnosis_suggestions(health)))
        layout.addWidget(QLabel("建议处理:"))
        layout.addWidget(suggestion_text)

        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("刷新状态")
        refresh_btn.clicked.connect(lambda: (dialog.close(), setattr(self, "_startup_health_panel", None), QTimer.singleShot(0, self.show_startup_health_panel)))
        diagnose_btn = QPushButton("一键诊断")
        diagnose_btn.clicked.connect(self.run_one_click_diagnosis)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.close)
        btn_layout.addWidget(refresh_btn)
        btn_layout.addWidget(diagnose_btn)
        btn_layout.addStretch(1)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        dialog.finished.connect(lambda *_args: setattr(self, "_startup_health_panel", None))
        self._startup_health_panel = dialog
        dialog.show()

    def build_diagnosis_report(self):
        """生成一键诊断报告。"""
        health = self.collect_environment_health()
        sections = []
        path_lines = [
            f"ADB 路径: {health.get('adb_path')}",
            f"ADB 来源: {health.get('adb_source')}",
            f"scrcpy 路径: {health.get('scrcpy_path')}",
            f"scrcpy 来源: {health.get('scrcpy_source')}",
            f"scrcpy-server 路径: {health.get('scrcpy_server_path') or '未设置'}",
            f"scrcpy-server 来源: {health.get('scrcpy_server_source')}",
        ]
        sections.append(("路径解析", "\n".join(path_lines)))
        ok, adb_devices_output = self._run_cli_capture([self.adb_path, "devices", "-l"])
        sections.append(("adb devices", adb_devices_output))

        ok, adb_version_output = self._run_cli_capture([self.adb_path, "version"])
        sections.append(("adb version", adb_version_output))

        ok, scrcpy_version_output = self._run_cli_capture([self.scrcpy_path, "--version"])
        sections.append(("scrcpy --version", scrcpy_version_output))

        statuses = health["device_entries"]
        status_lines = []
        offline_exists = False
        unauthorized_exists = False
        for item in statuses:
            status = item.get("status", "unknown")
            offline_exists = offline_exists or status == "offline"
            unauthorized_exists = unauthorized_exists or status == "unauthorized"
            status_lines.append(
                f"{item.get('model', '未知设备')} ({item.get('device_id')}) -> 状态: {status}, 连接: {item.get('transport', 'usb')}"
            )
        if not status_lines:
            status_lines.append("未检测到任何设备")
        status_lines.append(f"存在离线设备: {'是' if offline_exists else '否'}")
        status_lines.append(f"存在未授权设备: {'是' if unauthorized_exists else '否'}")
        sections.append(("设备授权/状态诊断", "\n".join(status_lines)))

        suggestion_lines = [f"- {item}" for item in self.build_diagnosis_suggestions(health)]
        sections.append(("建议处理", "\n".join(suggestion_lines)))

        report_lines = []
        for title, content in sections:
            report_lines.append(f"## {title}\n{content}\n")
        return "\n".join(report_lines).strip()

    def run_one_click_diagnosis(self):
        """执行一键诊断并展示结果。"""
        report = self.build_diagnosis_report()
        self.log("已生成一键诊断报告")

        dialog = QDialog(self)
        dialog.setWindowTitle("一键诊断")
        dialog.resize(760, 560)
        layout = QVBoxLayout(dialog)

        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(report)
        layout.addWidget(text_edit)

        btn_layout = QHBoxLayout()
        copy_btn = QPushButton("复制诊断结果")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(report))
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.close)
        btn_layout.addWidget(copy_btn)
        btn_layout.addStretch(1)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
        dialog.exec_()

    def _get_selected_device_entry(self):
        device_id = self.device_combo.currentData() if hasattr(self, 'device_combo') else None
        if not device_id:
            return None, None
        return device_id, self.device_status_map.get(device_id, {})

    def _get_selected_device_model(self):
        """获取当前选中设备的纯净型号名，避免夹带状态标签。"""
        _device_id, entry = self._get_selected_device_entry()
        model = (entry or {}).get("model")
        if model:
            return model
        if hasattr(self, 'device_combo') and self.device_combo.currentIndex() >= 0:
            text = self.device_combo.currentText()
            return text.split(' (')[0].lstrip('★ ').strip()
        return "未知设备"

    def _save_profile_for_device(self, device_id):
        """保存当前设备专属参数。"""
        if not device_id:
            return
        self.device_profiles[device_id] = self.config_service.collect_device_profile(self)

    def _apply_profile_for_device(self, device_id):
        """应用设备专属参数，没有则退回默认参数。"""
        if not device_id:
            return
        profile = self.device_profiles.get(device_id) or self.default_device_profile
        self._suspend_ui_reactions = True
        try:
            self.config_service.apply_device_profile(self, profile)
            self._sync_record_mode_options()
            self._update_crop_validation_state()
        finally:
            self._suspend_ui_reactions = False

    def _on_device_selection_changed(self, _index):
        """设备切换时保存上一台设备参数并恢复当前设备参数。"""
        current_id = self.device_combo.currentData() if hasattr(self, 'device_combo') else None
        previous_id = getattr(self, 'current_profile_device_id', None)

        if previous_id and previous_id != current_id:
            self._save_profile_for_device(previous_id)

        if current_id:
            self._apply_profile_for_device(current_id)

        self.current_profile_device_id = current_id
        self._update_selected_device_status_hint()

    def _apply_selected_preset(self):
        """将当前所选预设应用到界面。"""
        preset_name = self.preset_combo.currentText()
        if preset_name == "自定义":
            return
        self._suspend_ui_reactions = True
        try:
            if self.command_service.apply_preset_to_ui(self, preset_name):
                self._sync_record_mode_options()
                self._update_crop_validation_state()
                self.log(f"已应用参数预设：{preset_name}")
        finally:
            self._suspend_ui_reactions = False

    def _sync_record_mode_options(self):
        """同步纯录制/录屏/无窗口等互相关联的选项。"""
        if self.record_only_cb.isChecked():
            self.record_cb.setChecked(True)
            self.record_cb.setEnabled(False)
        else:
            self.record_cb.setEnabled(True)

    def _handle_record_only_changed(self, _state):
        """纯录制模式切换时同步提示与联动。"""
        self._sync_record_mode_options()
        if self._suspend_ui_reactions:
            return
        self._set_preset_custom_if_needed()
        if self.record_only_cb.isChecked():
            self.statusBar().showMessage("已启用纯录制模式：将自动开启录制，并以无窗口方式运行", 4000)
        else:
            self.statusBar().showMessage("已退出纯录制模式", 2500)

    def _set_preset_custom_if_needed(self, *_args):
        """用户手动修改参数后，将预设标记为自定义。"""
        if self._suspend_ui_reactions:
            return
        if hasattr(self, 'preset_combo') and self.preset_combo.currentText() != "自定义":
            self.preset_combo.setCurrentText("自定义")

    def _update_crop_validation_state(self, *_args):
        """即时校验裁剪参数格式。"""
        if not hasattr(self, 'crop_input'):
            return
        crop_value = self.crop_input.text().strip()
        if not crop_value:
            self.crop_input.setStyleSheet("")
            self.crop_input.setToolTip("裁剪格式：宽:高:X:Y")
            return

        _normalized, error = self.command_service._normalize_crop(crop_value)
        if error:
            self.crop_input.setStyleSheet("border: 1px solid #c85b52;")
            self.crop_input.setToolTip(error)
            if not self._suspend_ui_reactions:
                self.statusBar().showMessage(error, 3000)
        else:
            self.crop_input.setStyleSheet("")
            self.crop_input.setToolTip("裁剪格式有效")

    def _show_device_selection_hint(self, action_text="操作", use_dialog=False):
        """统一处理未选择设备时的提示。"""
        message = f"请先选择一个设备后再执行“{action_text}”"
        if hasattr(self, 'device_status_hint'):
            self.device_status_hint.setText(message)
            self.device_status_hint.setStyleSheet("color: #c85b52; font-weight: 600;")
            self.device_status_hint.hide()
        self.show_info_message("提示", message, log_message=message, show_dialog=use_dialog, duration=3000)

    def _reset_device_selection_hint_style(self):
        if hasattr(self, 'device_status_hint'):
            self.device_status_hint.setStyleSheet("color: #6e6a64;")
            self.device_status_hint.hide()

    def _apply_device_item_styles(self):
        """根据设备状态为下拉项设置颜色和提示。"""
        if not hasattr(self, 'device_combo'):
            return

        for combo in [self.device_combo]:
            if combo is None:
                continue
            for index in range(combo.count()):
                device_id = combo.itemData(index)
                entry = self.device_status_map.get(device_id, {})
                status = entry.get("status", "device")
                transport = entry.get("transport", "usb")
                is_running = device_id in self._get_running_device_ids()
                is_last = device_id == self.last_connected_device

                if status == "offline":
                    color = QColor(160, 90, 90)
                    tip = "设备当前离线，请检查数据线或网络连接"
                elif status == "unauthorized":
                    color = QColor(196, 120, 40)
                    tip = "设备未授权，请在手机上允许 USB 调试授权"
                elif is_running:
                    color = QColor(42, 122, 108)
                    tip = "设备正在投屏中"
                elif is_last:
                    color = QColor(186, 145, 46)
                    tip = "这是上次成功投屏的设备"
                else:
                    color = QColor(60, 60, 60) if transport == "usb" else QColor(66, 108, 180)
                    tip = "设备可用"

                combo.setItemData(index, color, Qt.ForegroundRole)
                combo.setItemData(index, tip, Qt.ToolTipRole)

    def _update_selected_device_status_hint(self):
        """根据当前选中设备刷新状态提示与按钮可用性。"""
        if not hasattr(self, 'device_status_hint'):
            return

        self._reset_device_selection_hint_style()

        device_id, entry = self._get_selected_device_entry()
        if not device_id:
            self.device_status_hint.setText("当前未选择设备")
            self.device_status_hint.hide()
            self.usb_btn.setEnabled(False)
            self.wifi_btn.setEnabled(False)
            return

        status = entry.get("status", "device")
        transport = entry.get("transport", "usb")
        is_running = device_id in self._get_running_device_ids()

        if status == "device":
            transport_text = "WiFi" if transport == "wifi" else "USB"
            hint = f"当前设备可用，连接方式：{transport_text}"
            if is_running:
                hint += "，并且正在投屏"
            self.usb_btn.setEnabled(True)
            self.wifi_btn.setEnabled(True)
        elif status == "offline":
            hint = "当前设备处于离线状态，请检查连接后再操作"
            self.usb_btn.setEnabled(False)
            self.wifi_btn.setEnabled(False)
        elif status == "unauthorized":
            hint = "当前设备未授权，请先在设备上允许调试授权"
            self.usb_btn.setEnabled(False)
            self.wifi_btn.setEnabled(False)
        else:
            hint = f"当前设备状态：{status}"
            self.usb_btn.setEnabled(False)
            self.wifi_btn.setEnabled(False)

        self.device_status_hint.setText(hint)
        self.device_status_hint.hide()

    def _ensure_selected_device_available(self, action_text):
        if self.device_combo.currentIndex() < 0:
            self._show_device_selection_hint(action_text)
            return None

        device_id, entry = self._get_selected_device_entry()
        if not device_id:
            self.show_warning_message("警告", "当前设备ID无效，请刷新设备列表后重试", show_dialog=True)
            return None

        status = entry.get("status", "device")
        if status != "device":
            status_label = "未授权" if status == "unauthorized" else ("离线" if status == "offline" else status)
            self.show_warning_message("警告", f"当前设备状态为“{status_label}”，无法执行{action_text}", show_dialog=True)
            return None

        return device_id

    def load_config(self):
        """加载本地配置并恢复到界面。"""
        self.config_service.load_into(self)

    def save_config(self):
        """保存当前界面配置。"""
        self.config_service.save_from(self)
    
    def cleanup_processes(self):
        """在应用程序关闭前清理所有进程"""
        if self._cleanup_done:
            return
        self._cleanup_done = True
        self.process_manager.cleanup_before_exit(
            main_process=self.process,
            event_monitor=self.event_monitor,
            timeout_ms=2000,
        )
        self.event_monitor = None
        
    def closeEvent(self, event):
        """重写关闭事件，确保进程被正确关闭"""
        self.save_config()
        self.cleanup_processes()
        super().closeEvent(event)
        
    def log(self, message):
        """向日志文本框中添加消息"""
        if not message:
            return
        
        # 检查应用是否正在关闭    
        if hasattr(self, 'is_closing') and self.is_closing:
            # 在关闭状态仅打印到控制台
            console_log(f"日志 (应用正在关闭): {message}")
            return
            
        # 检查控件是否有效
        if not hasattr(self, 'log_text') or self.log_text is None or not hasattr(self.log_text, "append"):
            console_log(f"日志 (控件无效): {message}", "WARN")  # 控件无效时打印到控制台
            return
            
        try:
            import datetime
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")

            level = self._classify_log_level(message)
            if self.log_entries and self.log_entries[-1]["message"] == message:
                self.log_entries[-1]["count"] += 1
                self.log_entries[-1]["timestamp"] = timestamp
            else:
                self.log_entries.append({
                    "timestamp": timestamp,
                    "message": message,
                    "level": level,
                    "count": 1,
                })

            self.last_log_message = message
            self.repeat_count = self.log_entries[-1]["count"]

            max_entries = 500
            if len(self.log_entries) > max_entries:
                self.log_entries = self.log_entries[-max_entries:]

            self._refresh_log_view()
            self._show_status_feedback(message, level)
            console_log(message, level.upper())
        except Exception as e:
            console_log(f"添加日志时出错: {e}, 消息: {message}", "ERROR")

    def _classify_log_level(self, message):
        """根据消息内容判定日志级别。"""
        message = (message or "").lower()
        if any(keyword in message for keyword in ["错误", "error", "exception", "traceback"]):
            return "error"
        if any(keyword in message for keyword in ["警告", "失败", "未检测到", "未授权", "离线", "重试", "无效"]):
            return "warning"
        return "info"

    def _get_visible_log_entries(self):
        """按当前过滤条件返回可见日志。"""
        if not hasattr(self, 'log_filter_combo'):
            return self.log_entries

        current_filter = self.log_filter_combo.currentText()
        if current_filter == "仅错误":
            return [item for item in self.log_entries if item["level"] == "error"]
        if current_filter == "警告及错误":
            return [item for item in self.log_entries if item["level"] in ("warning", "error")]
        return self.log_entries

    def _refresh_log_view(self, *_args):
        """根据当前日志缓存刷新日志显示。"""
        if not hasattr(self, 'log_text') or self.log_text is None:
            return

        color_map = {
            "info": "#2a2a2a",
            "warning": "#b06b00",
            "error": "#b03a37",
        }

        html_lines = []
        for item in self._get_visible_log_entries():
            message = html.escape(item["message"])
            suffix = f" <span style='color:#7b7770;'>(x{item['count']})</span>" if item["count"] > 1 else ""
            html_lines.append(
                f"<div style='color:{color_map.get(item['level'], '#2a2a2a')};'>"
                f"[{item['timestamp']}] {message}{suffix}</div>"
            )

        self.log_text.setHtml("".join(html_lines) or "")
        scrollbar = self.log_text.verticalScrollBar()
        if scrollbar:
            scrollbar.setValue(scrollbar.maximum())

    def _show_status_feedback(self, message, level):
        """把关键日志同步到状态栏。"""
        if level in ("warning", "error"):
            self.statusBar().showMessage(message, 3500)
        elif any(keyword in message for keyword in ["已启动", "已停止", "已成功", "已保存", "已应用参数预设", "日志已导出"]):
            self.statusBar().showMessage(message, 2500)

    def show_info_message(self, title, message, *, log_message=None, show_dialog=True, duration=3000):
        """统一的信息提示入口。"""
        final_log = log_message or message
        self.statusBar().showMessage(message, duration)
        self.log(final_log)
        if show_dialog:
            QMessageBox.information(self, title, message)

    def show_warning_message(self, title, message, *, log_message=None, show_dialog=True, duration=4000):
        """统一的警告提示入口。"""
        final_log = log_message or f"警告: {message}"
        self.statusBar().showMessage(message, duration)
        self.log(final_log)
        if show_dialog:
            QMessageBox.warning(self, title, message)

    def ask_confirmation(self, title, message, *, default=QMessageBox.No, log_message=None):
        """统一的确认对话框入口。"""
        if log_message:
            self.log(log_message)
        self.statusBar().showMessage(message, 2500)
        return QMessageBox.question(self, title, message, QMessageBox.Yes | QMessageBox.No, default)

    def copy_log(self):
        """复制当前可见日志到剪贴板。"""
        visible_entries = self._get_visible_log_entries()
        lines = []
        for item in visible_entries:
            suffix = f" (x{item['count']})" if item["count"] > 1 else ""
            lines.append(f"[{item['timestamp']}] {item['message']}{suffix}")
        QApplication.clipboard().setText("\n".join(lines))
        self.statusBar().showMessage("日志已复制到剪贴板", 2500)

    def export_log(self):
        """导出当前可见日志到文本文件。"""
        filename, _ = QFileDialog.getSaveFileName(self, "导出日志", "scrcpy_log.txt", "文本文件 (*.txt)")
        if not filename:
            return

        visible_entries = self._get_visible_log_entries()
        with open(filename, "w", encoding="utf-8") as f:
            for item in visible_entries:
                suffix = f" (x{item['count']})" if item["count"] > 1 else ""
                f.write(f"[{item['timestamp']}] {item['message']}{suffix}\n")
        self.log(f"日志已导出到: {filename}")

    def set_application_icon(self):
        """设置应用程序图标"""
        self.ui_support_service.set_window_icon(self)

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
            details = resolve_adb_path(
                preferred_path=(self.runtime_path_overrides or {}).get("adb_path"),
                return_details=True,
            )
            self.adb_resolution = details or {}
            return (details or {}).get("path", "adb")
        except Exception as e:
            self.log(f"查找adb路径出错: {e}")
            return 'adb'
        
    def find_scrcpy_path(self):
        """查找scrcpy路径"""
        try:
            details = resolve_scrcpy_path(
                preferred_path=(self.runtime_path_overrides or {}).get("scrcpy_path"),
                preferred_server_path=(self.runtime_path_overrides or {}).get("scrcpy_server_path"),
                return_details=True,
            )
            self.scrcpy_resolution = details or {}
            return (details or {}).get("path", "scrcpy")
        except Exception as e:
            self.log(f"查找scrcpy路径出错: {e}")
            return 'scrcpy'

    def _refresh_runtime_dependencies(self, *, save_config=True, announce=True):
        """按当前配置重新解析 adb/scrcpy 依赖并刷新控制器。"""
        self.adb_path = self.find_adb_path()
        self.scrcpy_path = self.find_scrcpy_path()
        self.controller = ScrcpyController(adb_path=self.adb_path, scrcpy_path=self.scrcpy_path)
        self.device_service = DeviceService(self.controller)
        self.wifi_service = WifiConnectionService(self, self.adb_path, self.process_manager)
        self.screenshot_service = ScreenshotService(self, self.controller)
        if save_config:
            self.save_config()
        if announce:
            self._log_runtime_dependency_status(show_dialog=False)

    def _log_runtime_dependency_status(self, *, show_dialog=False):
        """输出当前依赖解析结果。"""
        health = self.collect_environment_health()
        lines = [
            f"ADB: {health.get('adb_path')} (来源: {health.get('adb_source')})",
            f"scrcpy: {health.get('scrcpy_path')} (来源: {health.get('scrcpy_source')})",
            f"scrcpy-server: {health.get('scrcpy_server_path') or '未设置'} (来源: {health.get('scrcpy_server_source')})",
        ]
        self.log("环境依赖解析 -> " + " | ".join(lines))
        if show_dialog:
            self.show_info_message("环境依赖", "\n".join(lines), show_dialog=True, duration=2500)

    def _select_runtime_binary(self, key, title, filters):
        """选择运行时依赖文件并立即生效。"""
        current = (self.runtime_path_overrides or {}).get(key, "")
        filename, _ = QFileDialog.getOpenFileName(self, title, current, filters)
        if not filename:
            return
        self.runtime_path_overrides[key] = filename
        self._refresh_runtime_dependencies(save_config=True, announce=True)

    def _select_adb_path(self):
        self._select_runtime_binary("adb_path", "选择 ADB 可执行文件", "ADB 可执行文件 (adb.exe adb)")

    def _select_scrcpy_path(self):
        self._select_runtime_binary("scrcpy_path", "选择 scrcpy 可执行文件", "scrcpy 可执行文件 (scrcpy.exe scrcpy)")

    def _select_scrcpy_server_path(self):
        self._select_runtime_binary("scrcpy_server_path", "选择 scrcpy-server 文件", "scrcpy-server 文件 (scrcpy-server* *.jar)")

    def _reset_runtime_paths(self):
        self.runtime_path_overrides = {"adb_path": "", "scrcpy_path": "", "scrcpy_server_path": ""}
        self._refresh_runtime_dependencies(save_config=True, announce=True)
        
    def check_adb_available(self):
        """检查adb是否可用"""
        return check_command_available(self.adb_path, "version")
            
    def check_scrcpy_available(self):
        """检查scrcpy是否可用"""
        return check_command_available(self.scrcpy_path, "--version")

    def _create_device_group(self, scaled, compact_layout, layout_spacing):
        """创建设备连接区域。"""
        device_group = QGroupBox("设备连接")
        device_layout = QHBoxLayout(device_group)
        compact_layout(device_layout)

        device_label = QLabel("设备:")
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(scaled(220, 160))
        self.device_combo.currentIndexChanged.connect(self._on_device_selection_changed)

        self.device_status_hint = QLabel("当前未选择设备")
        self.device_status_hint.setStyleSheet("color: #6e6a64;")
        self.device_status_hint.hide()

        refresh_btn = QPushButton("刷新设备")
        refresh_btn.clicked.connect(lambda: self.check_devices(True))

        device_layout.addWidget(device_label)
        device_layout.addWidget(self.device_combo, 1)
        device_layout.addWidget(refresh_btn)

        self.usb_btn = QPushButton("一键USB连接")
        self.usb_btn.clicked.connect(self.start_scrcpy)
        self.usb_btn.setObjectName("usb_btn")

        self.wifi_btn = QPushButton("一键WIFI连接")
        self.wifi_btn.clicked.connect(self.connect_wireless)
        self.wifi_btn.setObjectName("wifi_btn")

        self.auto_refresh_cb = QCheckBox("自动刷新")
        self.auto_refresh_cb.setChecked(False)
        self.auto_refresh_cb.stateChanged.connect(self.toggle_auto_refresh)

        connection_layout = QHBoxLayout()
        compact_layout(connection_layout, margin_value=0, spacing_value=layout_spacing)
        connection_layout.addWidget(self.usb_btn)
        connection_layout.addWidget(self.wifi_btn)
        connection_layout.addStretch(1)
        connection_layout.addWidget(self.auto_refresh_cb)

        device_layout.addLayout(connection_layout)
        return device_group

    def _create_mirror_group(self, scaled, compact_layout):
        """创建镜像参数区域。"""
        mirror_group = QGroupBox("镜像模式")
        mirror_layout = QGridLayout(mirror_group)
        compact_layout(mirror_layout)

        preset_label = QLabel("参数预设:")
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(["自定义", *self.command_service.PRESETS.keys()])
        self.preset_combo.setMaximumWidth(scaled(140, 100))
        self.preset_combo.setToolTip("可快速应用一组常用投屏参数")

        preset_apply_btn = QPushButton("应用预设")
        preset_apply_btn.clicked.connect(self._apply_selected_preset)

        bitrate_label = QLabel("比特率:")
        self.bitrate_input = QLineEdit("6")
        self.bitrate_input.setMaximumWidth(scaled(72, 56))
        self.bitrate_input.textChanged.connect(self._set_preset_custom_if_needed)
        bitrate_unit = QLabel("Mbps")

        maxfps_label = QLabel("帧率:")
        self.maxfps_input = QLineEdit()
        self.maxfps_input.setPlaceholderText("默认")
        self.maxfps_input.setMaximumWidth(scaled(72, 56))
        self.maxfps_input.textChanged.connect(self._set_preset_custom_if_needed)
        fps_unit = QLabel("FPS")

        maxsize_label = QLabel("最大尺寸:")
        self.maxsize_input = QLineEdit("1080")
        self.maxsize_input.setMaximumWidth(scaled(72, 56))
        self.maxsize_input.textChanged.connect(self._set_preset_custom_if_needed)

        format_label = QLabel("录制格式:")
        self.format_combo = QComboBox()
        self.format_combo.addItems(["mp4", "mkv"])
        self.format_combo.setMaximumWidth(scaled(88, 70))
        self.format_combo.currentTextChanged.connect(self._set_preset_custom_if_needed)

        rotation_label = QLabel("限制方向:")
        self.rotation_combo = QComboBox()
        self.rotation_combo.addItems(["不限制", "横屏", "竖屏"])
        self.rotation_combo.setMaximumWidth(scaled(88, 70))
        self.rotation_combo.currentTextChanged.connect(self._set_preset_custom_if_needed)

        codec_label = QLabel("编码器:")
        self.codec_combo = QComboBox()
        self.codec_combo.addItems(["默认", "h264", "h265", "av1"])
        self.codec_combo.setMaximumWidth(scaled(100, 80))
        self.codec_combo.currentTextChanged.connect(self._set_preset_custom_if_needed)

        displayid_label = QLabel("显示ID:")
        self.displayid_input = QLineEdit()
        self.displayid_input.setPlaceholderText("默认")
        self.displayid_input.setMaximumWidth(scaled(72, 56))
        self.displayid_input.textChanged.connect(self._set_preset_custom_if_needed)

        crop_label = QLabel("裁剪:")
        self.crop_input = QLineEdit()
        self.crop_input.setPlaceholderText("宽:高:X:Y")
        self.crop_input.setToolTip("裁剪格式：宽:高:X:Y")
        self.crop_input.textChanged.connect(self._set_preset_custom_if_needed)
        self.crop_input.textChanged.connect(self._update_crop_validation_state)

        record_label = QLabel("录制存储路径:")
        self.record_path = QLineEdit()
        self.record_path.setPlaceholderText("默认不录制")
        self.record_path.textChanged.connect(self._set_preset_custom_if_needed)

        browse_btn = QPushButton("选择路径")
        browse_btn.clicked.connect(self.select_record_path)

        mirror_layout.addWidget(preset_label, 0, 0)
        mirror_layout.addWidget(self.preset_combo, 0, 1)
        mirror_layout.addWidget(preset_apply_btn, 0, 2)
        mirror_layout.addWidget(codec_label, 0, 3)
        mirror_layout.addWidget(self.codec_combo, 0, 4)

        mirror_layout.addWidget(bitrate_label, 1, 0)
        mirror_layout.addWidget(self.bitrate_input, 1, 1)
        mirror_layout.addWidget(bitrate_unit, 1, 2)
        mirror_layout.addWidget(maxsize_label, 1, 3)
        mirror_layout.addWidget(self.maxsize_input, 1, 4)
        mirror_layout.addWidget(maxfps_label, 1, 5)
        mirror_layout.addWidget(self.maxfps_input, 1, 6)
        mirror_layout.addWidget(fps_unit, 1, 7)

        mirror_layout.addWidget(format_label, 2, 0)
        mirror_layout.addWidget(self.format_combo, 2, 1)
        mirror_layout.addWidget(rotation_label, 2, 3)
        mirror_layout.addWidget(self.rotation_combo, 2, 4)
        mirror_layout.addWidget(displayid_label, 2, 5)
        mirror_layout.addWidget(self.displayid_input, 2, 6)

        mirror_layout.addWidget(crop_label, 3, 0)
        mirror_layout.addWidget(self.crop_input, 3, 1, 1, 6)

        mirror_layout.addWidget(record_label, 4, 0)
        mirror_layout.addWidget(self.record_path, 4, 1, 1, 5)
        mirror_layout.addWidget(browse_btn, 4, 6, 1, 2)
        return mirror_group

    def _create_options_group(self, scaled, compact_layout):
        """创建功能选项区域。"""
        options_group = QGroupBox("功能选项")
        options_layout = QGridLayout(options_group)
        compact_layout(options_layout)

        self.record_cb = QCheckBox("录制屏幕")
        self.fullscreen_cb = QCheckBox("全屏显示")
        self.always_top_cb = QCheckBox("窗口置顶")
        self.show_touches_cb = QCheckBox("显示触摸")
        self.no_control_cb = QCheckBox("无交互")
        self.disable_clipboard_cb = QCheckBox("禁用剪贴板")
        self.turn_screen_off_cb = QCheckBox("投屏时熄屏")
        self.stay_awake_cb = QCheckBox("保持唤醒")
        self.record_only_cb = QCheckBox("纯录制模式")
        self.record_only_cb.setToolTip("启用后将自动打开录屏，并以无窗口方式运行")
        self.record_only_cb.stateChanged.connect(self._handle_record_only_changed)

        for checkbox in [
            self.record_cb,
            self.fullscreen_cb,
            self.always_top_cb,
            self.show_touches_cb,
            self.no_control_cb,
            self.disable_clipboard_cb,
            self.turn_screen_off_cb,
            self.stay_awake_cb,
        ]:
            checkbox.stateChanged.connect(self._set_preset_custom_if_needed)

        self.always_top_cb.stateChanged.connect(self._handle_always_on_top_changed)

        options_layout.addWidget(self.record_cb, 0, 0)
        options_layout.addWidget(self.fullscreen_cb, 0, 1)
        options_layout.addWidget(self.always_top_cb, 0, 2)
        options_layout.addWidget(self.show_touches_cb, 1, 0)
        options_layout.addWidget(self.no_control_cb, 1, 1)
        options_layout.addWidget(self.disable_clipboard_cb, 1, 2)
        options_layout.addWidget(self.turn_screen_off_cb, 2, 0)
        options_layout.addWidget(self.stay_awake_cb, 2, 1)
        options_layout.addWidget(self.record_only_cb, 2, 2)
        return options_group

    def _create_log_group(self):
        """创建日志区域。"""
        log_group = QGroupBox("操作日志")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(8, 8, 8, 8)
        log_layout.setSpacing(4)

        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(4)
        toolbar_layout.addWidget(QLabel("日志过滤:"))

        self.log_filter_combo = QComboBox()
        self.log_filter_combo.addItems(["全部", "警告及错误", "仅错误"])
        self.log_filter_combo.currentTextChanged.connect(self._refresh_log_view)
        self.log_filter_combo.setMaximumWidth(120)
        toolbar_layout.addWidget(self.log_filter_combo)
        toolbar_layout.addStretch(1)

        copy_log_btn = QPushButton("复制日志")
        copy_log_btn.clicked.connect(self.copy_log)
        copy_log_btn.setMaximumWidth(110)

        export_log_btn = QPushButton("导出日志")
        export_log_btn.clicked.connect(self.export_log)
        export_log_btn.setMaximumWidth(110)

        toolbar_layout.addWidget(copy_log_btn)
        toolbar_layout.addWidget(export_log_btn)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(170)

        log_layout.addLayout(toolbar_layout)
        log_layout.addWidget(self.log_text, 1)
        return log_group

    def _create_bottom_action_bar(self):
        """创建底部主操作按钮区域。"""
        action_widget = QWidget()
        action_layout = QHBoxLayout(action_widget)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(8)

        clear_log_btn = QPushButton("清空日志")
        clear_log_btn.clicked.connect(self.clear_log)
        clear_log_btn.setObjectName("clear_log_btn")

        stop_btn = QPushButton("停止投屏")
        stop_btn.clicked.connect(self.stop_scrcpy)
        stop_btn.setObjectName("stop_btn")

        screenshot_btn = QPushButton("截图")
        screenshot_btn.clicked.connect(self.take_screenshot)
        screenshot_btn.setObjectName("screenshot_btn")

        action_layout.addWidget(clear_log_btn)
        action_layout.addWidget(stop_btn)
        action_layout.addWidget(screenshot_btn)
        return action_widget
        
    def initUI(self):
        # 设置窗口
        self.setWindowTitle('Scrcpy GUI - 安卓屏幕控制')
        # 根据屏幕可用尺寸智能自适应，避免默认窗口过高
        screen = QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else None
        base_w, base_h = 800, 620
        if avail:
            w = avail.width()
            h = avail.height()
            # 高度再回调一档，保持紧凑但不挤压日志与底栏
            frac_w = 0.46 if w < 1920 else 0.38
            frac_h = 0.44 if h < 1080 else 0.39
            base_w = max(640, min(int(w * frac_w), 900))
            base_h = max(580, min(int(h * frac_h), 660))
        self.resize(base_w, base_h)
        self.setMinimumSize(700, 520)
        
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
        device_group = self._create_device_group(scaled, compact_layout, layout_spacing)
        mirror_group = self._create_mirror_group(scaled, compact_layout)
        options_group = self._create_options_group(scaled, compact_layout)
        log_group = self._create_log_group()
        bottom_action_bar = self._create_bottom_action_bar()

        main_layout.addWidget(device_group)
        main_layout.addWidget(mirror_group)
        main_layout.addWidget(options_group)
        main_layout.addWidget(log_group, 1)
        main_layout.addWidget(bottom_action_bar)
        
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

        self.disconnect_wifi_action = QAction("断开WiFi连接", self)
        self.disconnect_wifi_action.triggered.connect(self.disconnect_wireless)
        device_menu.addAction(self.disconnect_wifi_action)

        
        # 工具菜单
        tools_menu = menu_bar.addMenu("工具")
        
        screenshot_action = QAction("截图", self)
        screenshot_action.triggered.connect(self.take_screenshot)
        tools_menu.addAction(screenshot_action)

        quick_screenshot_action = QAction("快速截图到默认目录", self)
        quick_screenshot_action.triggered.connect(self.screenshot_service.quick_save_screenshot)
        tools_menu.addAction(quick_screenshot_action)

        self.quick_screenshot_mode_action = QAction("启用截图快速保存模式", self)
        self.quick_screenshot_mode_action.setCheckable(True)
        tools_menu.addAction(self.quick_screenshot_mode_action)

        self.screenshot_date_archive_action = QAction("截图按日期归档", self)
        self.screenshot_date_archive_action.setCheckable(True)
        tools_menu.addAction(self.screenshot_date_archive_action)

        set_screenshot_dir_action = QAction("设置截图默认目录", self)
        set_screenshot_dir_action.triggered.connect(self.select_screenshot_dir)
        tools_menu.addAction(set_screenshot_dir_action)

        tools_menu.addSeparator()
        set_adb_path_action = QAction("设置 ADB 路径", self)
        set_adb_path_action.triggered.connect(self._select_adb_path)
        tools_menu.addAction(set_adb_path_action)

        set_scrcpy_path_action = QAction("设置 scrcpy 路径", self)
        set_scrcpy_path_action.triggered.connect(self._select_scrcpy_path)
        tools_menu.addAction(set_scrcpy_path_action)

        set_scrcpy_server_action = QAction("设置 scrcpy-server 路径", self)
        set_scrcpy_server_action.triggered.connect(self._select_scrcpy_server_path)
        tools_menu.addAction(set_scrcpy_server_action)

        reset_runtime_paths_action = QAction("恢复自动检测依赖路径", self)
        reset_runtime_paths_action.triggered.connect(self._reset_runtime_paths)
        tools_menu.addAction(reset_runtime_paths_action)

        tools_menu.addSeparator()
        self.open_record_dir_action = QAction("录屏完成后打开目录", self)
        self.open_record_dir_action.setCheckable(True)
        tools_menu.addAction(self.open_record_dir_action)

        self.open_record_file_action = QAction("录屏完成后打开文件", self)
        self.open_record_file_action.setCheckable(True)
        tools_menu.addAction(self.open_record_file_action)

        
        # 添加应用管理器入口到工具菜单
        app_manager_action = QAction("应用管理器", self)
        app_manager_action.triggered.connect(self.show_app_manager)
        tools_menu.addAction(app_manager_action)
        
        # 帮助菜单
        help_menu = menu_bar.addMenu("帮助")

        health_action = QAction("环境自检", self)
        health_action.triggered.connect(self.show_startup_health_panel)
        help_menu.addAction(health_action)

        diagnose_action = QAction("一键诊断", self)
        diagnose_action.triggered.connect(self.run_one_click_diagnosis)
        help_menu.addAction(diagnose_action)
        help_menu.addSeparator()
        
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

    def select_screenshot_dir(self):
        """选择默认截图保存目录。"""
        directory = QFileDialog.getExistingDirectory(self, "选择截图默认目录", self.screenshot_dir or "")
        if directory:
            self.screenshot_dir = directory
            self.show_info_message("截图目录", f"默认截图目录已设置为：{directory}", show_dialog=False, duration=2500)
            
    def clear_log(self):
        """清空日志文本框"""
        self.log_entries.clear()
        self.log_text.clear()
        self.statusBar().showMessage("日志已清空", 2000)

    def create_control_bar(self, device_id, window_title):
        """兼容旧版本调用，当前版本不再创建额外控制栏。"""
        if device_id not in self.control_bars:
            self.control_bars[device_id] = None
            self.log(f"设备 {device_id} 的独立控制栏功能当前已禁用，已跳过创建")
        return True
            
    def check_devices(self, show_message=False):
        """检查连接的设备并更新设备列表
        
        Args:
            show_message: 是否显示设备检测消息，默认为False
        """
        try:
            previous_device = self.device_combo.currentData() or self.pending_selected_device or self.last_connected_device
            devices, selected_device = self.device_service.sync_device_widgets(
                self.device_combo,
                preferred_device_id=previous_device,
                active_device_ids=self._get_running_device_ids(),
                last_connected_device_id=self.last_connected_device,
            )
            self.device_status_map = {item["device_id"]: item for item in devices}
            self._apply_device_item_styles()
            
            # 更新连接按钮状态
            available_devices = [item for item in devices if item.get("status") == "device"]
            has_devices = len(available_devices) > 0
            if hasattr(self, 'disconnect_wifi_action'):
                has_wifi_devices = any(item.get("transport") == "wifi" and item.get("status") == "device" for item in devices)
                self.disconnect_wifi_action.setEnabled(has_wifi_devices)
            self._update_selected_device_status_hint()
            
            # 只有当show_message为True或自动刷新开启时才显示无设备消息
            if not has_devices and (show_message or (hasattr(self, 'auto_refresh_cb') and self.auto_refresh_cb.isChecked())):
                self.log("未检测到设备，请检查设备连接")
            elif has_devices and show_message:
                offline_count = sum(1 for item in devices if item.get("status") == "offline")
                unauthorized_count = sum(1 for item in devices if item.get("status") == "unauthorized")
                extra = []
                if offline_count:
                    extra.append(f"离线 {offline_count}")
                if unauthorized_count:
                    extra.append(f"未授权 {unauthorized_count}")
                suffix = f"（{'，'.join(extra)}）" if extra else ""
                self.log(f"检测到 {len(available_devices)} 个可用设备{suffix}")
                self.pending_selected_device = selected_device
            
            return devices
        except Exception as e:
            if show_message:
                self.log(f"检查设备出错: {e}")
            return []
        
    def start_scrcpy(self):
        """启动scrcpy进程"""
        device_id = self._ensure_selected_device_available("投屏")
        if not device_id:
            return
            
        # 检查设备是否已经连接
        if device_id in self.device_processes and self.device_processes[device_id].state() == QProcess.Running:
            self.log(f"设备 {device_id} 已经在运行")
            return
            
        device_model = self._get_selected_device_model()
        cmd = self._build_single_device_command(
            device_id,
            f"{device_model} - {device_id}",
            window_x=100,
            window_y=100,
        )
        if not cmd:
            return
        
        # 启动进程
        self.log(f"启动设备 {device_id} 镜像: {' '.join(cmd)}")
        
        try:
            self._launch_device_process(device_id, cmd, f"已启动设备 {device_id} 的 scrcpy 进程")
            
        except Exception as e:
            self.log(f"启动 scrcpy 失败: {str(e)}")
            if device_id in self.device_processes:
                del self.device_processes[device_id]

    def create_process_finished_handler(self, device_id):
        """创建进程结束处理器"""
        def handler(exit_code, exit_status):
            # 进程结束处理
            self.log(f"设备 {device_id} 的 scrcpy 进程已结束 (代码: {exit_code})")
            record_path = self.record_outputs.pop(device_id, None)
            if exit_code == 0 and record_path:
                QTimer.singleShot(300, lambda path=record_path, dev=device_id: self._handle_recording_finished(dev, path))
            
            # 从进程字典中移除
            if device_id in self.device_processes:
                del self.device_processes[device_id]
            QTimer.singleShot(0, lambda: self.check_devices(False))
                
        return handler
        
    def stop_scrcpy(self):
        """停止scrcpy进程"""
        if self.device_combo.currentIndex() < 0:
            # 如果没有选择设备，直接停止所有进程
            self.stop_all_scrcpy()
            return
            
        device_id = self.device_combo.currentData()
        
        if device_id in self.device_processes:
            if not self.process_manager.stop_device_process(device_id, timeout_ms=2000):
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
        self.process_manager.stop_all_processes(timeout_ms)

        if hasattr(self, 'process') and self.process and self.process.state() == QProcess.Running:
            try:
                self.process.disconnect()
                self.process.kill()
                self.process.waitForFinished(timeout_ms)
            except Exception as e:
                console_log(f"终止主进程时出错: {e}", "ERROR")

    def handle_process_output(self, process, device_id):
        """处理指定进程的标准输出"""
        data = decode_process_output(process.readAllStandardOutput())
        if data.strip():
            self.log(f"[{device_id}] {data.strip()}")
            
    def handle_process_error(self, process, device_id):
        """处理指定进程的标准错误"""
        data = decode_process_output(process.readAllStandardError())
        if data.strip():
            cleaned = data.strip()
            if self._looks_like_informational_output(cleaned):
                self.log(f"[{device_id}] {cleaned}")
            else:
                self.log(f"[{device_id}] 错误: {cleaned}")
            
    def handle_process_finished(self, device_id):
        """处理进程结束事件"""
        if device_id in self.device_processes:
            del self.device_processes[device_id]
            self.log(f"设备 {device_id} 的进程已结束")
            
    def connect_wireless(self):
        """通过无线方式连接设备"""
        device_id = self._ensure_selected_device_available("WiFi连接")
        if not device_id:
            return
            
        self.wifi_service.connect_device(device_id)

    def disconnect_wireless(self):
        """断开当前或全部 WiFi 设备连接。"""
        device_id, entry = self._get_selected_device_entry()
        targets = []
        if device_id and entry.get("transport") == "wifi" and entry.get("status") == "device":
            targets = [device_id]
        else:
            targets = [
                item["device_id"] for item in self.device_status_map.values()
                if item.get("transport") == "wifi" and item.get("status") == "device"
            ]

        if not targets:
            self.show_info_message("提示", "当前没有可断开的 WiFi 设备", show_dialog=True)
            return

        if len(targets) > 1 and (not device_id or device_id not in targets):
            reply = self.ask_confirmation(
                "断开 WiFi 设备",
                f"检测到 {len(targets)} 个 WiFi 设备，是否全部断开？",
                default=QMessageBox.Yes,
            )
            if reply != QMessageBox.Yes:
                return

        for target in targets:
            if target in self.device_processes:
                self.process_manager.stop_device_process(target, timeout_ms=1500)
            success, message = self.wifi_service.disconnect_wireless_device(target)
            if success:
                self.log(f"已断开 WiFi 设备 {target}: {message.strip()}")
            else:
                self.log(f"断开 WiFi 设备 {target} 失败: {message}")

        QTimer.singleShot(500, lambda: self.check_devices(True))
        
    def do_connect_wireless(self, ip_address, original_device_id=None):
        """实际执行无线连接"""
        self.wifi_service.do_connect_wireless(ip_address, original_device_id)
            
    def start_scrcpy_with_ip(self, ip_address, original_device_id=None):
        """使用指定的IP地址启动scrcpy"""
        # 更新设备列表
        devices = self.device_service.list_devices()
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
            self.last_connected_device = wireless_device_id
            
            # 启动 scrcpy
            self.start_scrcpy()
        else:
            self.log(f"无法找到无线连接的设备 {ip_address}")
            
    def handle_stdout(self):
        """处理标准输出"""
        data = decode_process_output(self.process.readAllStandardOutput())
        if data.strip():
            self.log(data.strip())
            
    def handle_stderr(self):
        """处理标准错误"""
        data = decode_process_output(self.process.readAllStandardError())
        if data.strip():
            cleaned = data.strip()
            if self._looks_like_informational_output(cleaned):
                self.log(cleaned)
            else:
                self.log(f"错误: {cleaned}")

    def _looks_like_informational_output(self, text):
        """判断 stderr 是否更像普通信息而非真正错误。"""
        text = (text or "").strip()
        if not text:
            return False
        upper = text.upper()
        if any(keyword in upper for keyword in ["ERROR", "EXCEPTION", "FAILED"]):
            return False
        markers = ["INFO:", "[SERVER] INFO:", "file pushed", "Renderer:", "Texture:", "Device:"]
        return any(marker.lower() in text.lower() for marker in markers)
    
    def take_screenshot(self):
        """截取设备屏幕并保存到电脑"""
        self.screenshot_service.take_screenshot()

    def show_about(self):
        """显示关于对话框"""
        self.ui_support_service.show_about(self)

    def show_app_manager(self):
        """显示应用管理器对话框"""
        # 获取当前选择的设备ID
        device_id = None
        if self.device_combo.currentIndex() >= 0:
            device_id = self.device_combo.currentData()

        self.ui_support_service.show_app_manager(self, self.controller, device_id=device_id)


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
    
    ui_support_service = UISupportService()
    ui_support_service.set_application_icon(app)
    
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
