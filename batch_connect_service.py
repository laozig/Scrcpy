#!/usr/bin/env python
# -*- coding: utf-8 -*-

from functools import partial

from PyQt5.QtCore import QProcess, QTimer
from PyQt5.QtWidgets import QMessageBox


class BatchConnectService:
    """负责批量连接设备与延迟控制栏兼容逻辑。"""

    def __init__(self, owner):
        self.owner = owner

    def connect_all_devices(self):
        devices = self.owner.device_service.list_devices()
        if not devices:
            if hasattr(self.owner, 'show_warning_message'):
                self.owner.show_warning_message("警告", "未检测到设备", show_dialog=True)
            else:
                QMessageBox.warning(self.owner, "警告", "未检测到设备")
            return

        if self.owner.device_processes:
            if hasattr(self.owner, 'ask_confirmation'):
                reply = self.owner.ask_confirmation(
                    "已有设备运行",
                    "是否先停止当前所有设备进程？",
                    default=QMessageBox.Yes,
                )
            else:
                reply = QMessageBox.question(
                    self.owner,
                    "已有设备运行",
                    "是否先停止当前所有设备进程？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes,
                )
            if reply == QMessageBox.Yes:
                self.owner.stop_all_scrcpy()

        pending_devices = []
        already_running = []
        for device_id, model in devices:
            if device_id in self.owner.device_processes and self.owner.device_processes[device_id].state() == QProcess.Running:
                already_running.append((device_id, model))
            else:
                pending_devices.append((device_id, model))

        if already_running:
            running_names = "、".join([f"{model} ({device_id})" for device_id, model in already_running])
            self.owner.log(f"以下设备已在投屏中，已跳过: {running_names}")

        connect_only_new = True
        if hasattr(self.owner, 'connect_only_new_action'):
            connect_only_new = self.owner.connect_only_new_action.isChecked()

        if not connect_only_new and already_running:
            pending_devices = devices

        count = 0
        positions = self.owner.get_multi_device_window_positions(len(pending_devices))
        for index, (device_id, model) in enumerate(pending_devices):
            if device_id in self.owner.device_processes and self.owner.device_processes[device_id].state() == QProcess.Running:
                self.owner.log(f"设备 {model} ({device_id}) 已经在运行")
                continue

            window_x, window_y = positions[index] if index < len(positions) else (100 + count * 50, 100 + count * 50)

            cmd = self.owner._build_single_device_command(
                device_id,
                f"Scrcpy - {model} ({device_id})",
                window_x=window_x,
                window_y=window_y,
            )
            if not cmd:
                continue

            try:
                window_title = f"Scrcpy - {model} ({device_id})"
                self.owner._launch_device_process(
                    device_id,
                    cmd,
                    f"已启动设备 {model} ({device_id}) 的 scrcpy 进程",
                )
                count += 1
                self._schedule_control_bar_retry(device_id, window_title)
            except Exception as e:
                self.owner.log(f"启动设备 {model} ({device_id}) 失败: {str(e)}")
                if device_id in self.owner.device_processes:
                    del self.owner.device_processes[device_id]

        if count > 0:
            self.owner.log(f"成功连接 {count} 个设备")
        elif already_running:
            self.owner.log("所有可检测设备均已在投屏中")

    def _schedule_control_bar_retry(self, device_id, window_title):
        delay_times = [2000, 3500, 5000, 7000, 10000]

        def attempt_create_control_bar(d_id, w_title, attempt_index=0):
            if attempt_index >= len(delay_times):
                self.owner.log(f"⚠️ 设备 {d_id} 控制栏创建尝试已达最大次数")
                return

            success = self.owner.create_control_bar(d_id, w_title)
            if not success and attempt_index + 1 < len(delay_times):
                next_delay = delay_times[attempt_index + 1] - delay_times[attempt_index]
                self.owner.log(f"设备 {d_id}: 将在 {next_delay/1000} 秒后再次尝试创建控制栏")
                QTimer.singleShot(next_delay, partial(attempt_create_control_bar, d_id, w_title, attempt_index + 1))

        QTimer.singleShot(delay_times[0], partial(attempt_create_control_bar, device_id, window_title, 0))