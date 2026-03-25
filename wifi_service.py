#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt5.QtCore import QProcess, QTimer

from utils import decode_process_output


class WifiConnectionService:
    """封装无线连接流程及其异步回调链。"""

    def __init__(self, owner, adb_path, process_manager):
        self.owner = owner
        self.adb_path = adb_path
        self.process_manager = process_manager
        self.tcpip_retry_limit = 1
        self.ip_retry_limit = 1
        self.connect_retry_limit = 2

    def connect_device(self, device_id, tcpip_attempt=0):
        self.owner.log("正在获取设备 IP 地址...")
        temp_process = self.process_manager.track_process(QProcess(self.owner))
        temp_process.finished.connect(
            lambda _code, _status, proc=temp_process, dev=device_id: self._handle_ip_before_tcpip_finished(proc, dev, 0)
        )
        temp_process.start(self.adb_path, ['-s', device_id, 'shell', 'ip', 'route'])

    def _handle_ip_before_tcpip_finished(self, process, device_id, ip_attempt=0):
        if process.exitCode() != 0:
            error = decode_process_output(process.readAllStandardError())
            if ip_attempt < self.ip_retry_limit:
                self.owner.log(f"获取 IP 地址失败，正在重试({ip_attempt + 1}/{self.ip_retry_limit + 1}): {error}")
                QTimer.singleShot(1000, lambda: self._retry_ip_before_tcpip(device_id, ip_attempt + 1))
                return
            self.owner.log(f"获取 IP 地址失败: {error}")
            return

        output = decode_process_output(process.readAllStandardOutput())
        ip_address = self._extract_wlan_ip(output)
        if not ip_address:
            if ip_attempt < self.ip_retry_limit:
                self.owner.log(f"未解析到设备 IP，正在重试({ip_attempt + 1}/{self.ip_retry_limit + 1})...")
                QTimer.singleShot(1000, lambda: self._retry_ip_before_tcpip(device_id, ip_attempt + 1))
                return
            self.owner.log("无法获取设备 IP 地址，请确保设备已连接到WiFi")
            return

        self.owner.log(f"已找到设备 IP: {ip_address}")
        self._switch_device_to_tcpip(device_id, ip_address, tcpip_attempt=0)

    def _retry_ip_before_tcpip(self, device_id, ip_attempt):
        self.owner.log("正在重新获取设备 IP 地址...")
        temp_process = self.process_manager.track_process(QProcess(self.owner))
        temp_process.finished.connect(
            lambda _code, _status, proc=temp_process, dev=device_id, attempt=ip_attempt: self._handle_ip_before_tcpip_finished(proc, dev, attempt)
        )
        temp_process.start(self.adb_path, ['-s', device_id, 'shell', 'ip', 'route'])

    def _switch_device_to_tcpip(self, device_id, ip_address, tcpip_attempt=0):
        self.owner.log(f"正在将设备 {device_id} 切换到 TCP/IP 模式...")
        temp_process = self.process_manager.track_process(QProcess(self.owner))
        temp_process.finished.connect(
            lambda _code, _status, proc=temp_process, dev=device_id, ip=ip_address, attempt=tcpip_attempt: self._handle_tcpip_finished(proc, dev, ip, attempt)
        )
        temp_process.start(self.adb_path, ['-s', device_id, 'tcpip', '5555'])

    def _handle_tcpip_finished(self, process, device_id, ip_address, tcpip_attempt=0):
        if process.exitCode() != 0:
            error = decode_process_output(process.readAllStandardError())
            if tcpip_attempt < self.tcpip_retry_limit:
                self.owner.log(f"切换到 TCP/IP 模式失败，正在重试({tcpip_attempt + 1}/{self.tcpip_retry_limit + 1}): {error}")
                QTimer.singleShot(1200, lambda: self._switch_device_to_tcpip(device_id, ip_address, tcpip_attempt + 1))
                return
            self.owner.log(f"切换到 TCP/IP 模式失败: {error}")
            return

        self.owner.log(f"设备已切换到 TCP/IP 模式，准备连接 {ip_address}:5555...")
        QTimer.singleShot(1800, lambda: self.do_connect_wireless(ip_address, device_id, 0))

    def _retry_ip_route(self, device_id, ip_attempt):
        self.owner.log("正在重新获取设备 IP 地址...")
        temp_process = self.process_manager.track_process(QProcess(self.owner))
        temp_process.finished.connect(
            lambda _code, _status, proc=temp_process, dev=device_id, attempt=ip_attempt: self._handle_ip_route_finished(proc, dev, attempt)
        )
        temp_process.start(self.adb_path, ['-s', device_id, 'shell', 'ip', 'route'])

    def _handle_ip_route_finished(self, process, device_id, ip_attempt=0):
        if process.exitCode() != 0:
            error = decode_process_output(process.readAllStandardError())
            if ip_attempt < self.ip_retry_limit:
                self.owner.log(f"获取 IP 地址失败，正在重试({ip_attempt + 1}/{self.ip_retry_limit + 1}): {error}")
                QTimer.singleShot(1000, lambda: self._retry_ip_route(device_id, ip_attempt + 1))
                return
            self.owner.log(f"获取 IP 地址失败: {error}")
            return

        output = decode_process_output(process.readAllStandardOutput())
        ip_address = None
        for line in output.strip().split('\n'):
            if "wlan0" in line and "src" in line:
                parts = line.split()
                ip_index = parts.index("src")
                if ip_index + 1 < len(parts):
                    ip_address = parts[ip_index + 1]
                    break

        if not ip_address:
            if ip_attempt < self.ip_retry_limit:
                self.owner.log(f"未解析到设备 IP，正在重试({ip_attempt + 1}/{self.ip_retry_limit + 1})...")
                QTimer.singleShot(1000, lambda: self._retry_ip_route(device_id, ip_attempt + 1))
                return
            self.owner.log("无法获取设备 IP 地址，请确保设备已连接到WiFi")
            return

        self.owner.log(f"已找到设备 IP: {ip_address}，等待设备准备就绪...")
        QTimer.singleShot(2000, lambda: self.do_connect_wireless(ip_address, device_id, 0))

    def _extract_wlan_ip(self, output):
        ip_address = None
        for line in output.strip().split('\n'):
            if "wlan0" in line and "src" in line:
                parts = line.split()
                if "src" in parts:
                    ip_index = parts.index("src")
                    if ip_index + 1 < len(parts):
                        ip_address = parts[ip_index + 1]
                        break
        return ip_address

    def do_connect_wireless(self, ip_address, original_device_id=None, connect_attempt=0):
        self.owner.log(f"正在连接到 {ip_address}:5555...")
        temp_process = self.process_manager.track_process(QProcess(self.owner))
        temp_process.finished.connect(
            lambda _code, _status, proc=temp_process, ip=ip_address, orig=original_device_id, attempt=connect_attempt: self._handle_wireless_connect_finished(proc, ip, orig, attempt)
        )
        temp_process.start(self.adb_path, ['connect', f"{ip_address}:5555"])

    def _handle_wireless_connect_finished(self, process, ip_address, original_device_id=None, connect_attempt=0):
        output = decode_process_output(process.readAllStandardOutput())
        error = decode_process_output(process.readAllStandardError())
        normalized = f"{output} {error}".lower()
        if process.exitCode() == 0 and ("connected" in normalized or "already connected" in normalized):
            self.owner.log(f"已成功连接到 {ip_address}:5555")
            QTimer.singleShot(500, lambda: self.owner.check_devices(True))
            QTimer.singleShot(1500, lambda: self.owner.start_scrcpy_with_ip(ip_address, original_device_id))
        else:
            if connect_attempt < self.connect_retry_limit:
                self.owner.log(
                    f"连接失败，正在重试({connect_attempt + 1}/{self.connect_retry_limit + 1}): {output} {error}"
                )
                QTimer.singleShot(1500, lambda: self.do_connect_wireless(ip_address, original_device_id, connect_attempt + 1))
                return
            self.owner.log(f"连接失败: {output} {error}")

    def disconnect_wireless_device(self, device_id):
        """断开指定的无线设备连接。"""
        target = device_id if device_id and ":" in device_id else None
        return self.owner.controller.disconnect_device(target)