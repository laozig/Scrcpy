#!/usr/bin/env python
# -*- coding: utf-8 -*-


class DeviceService:
    """负责设备发现与设备列表控件同步。"""

    def __init__(self, controller):
        self.controller = controller

    def list_devices(self):
        """获取设备列表。"""
        return self.controller.get_devices()

    def list_device_entries(self, active_device_ids=None, last_connected_device_id=None):
        """获取带状态与展示文本的设备条目。"""
        active_device_ids = set(active_device_ids or [])
        if hasattr(self.controller, "get_device_statuses"):
            raw_devices = self.controller.get_device_statuses()
        else:
            raw_devices = [
                {
                    "device_id": device_id,
                    "status": "device",
                    "model": model,
                    "transport": "wifi" if ":" in device_id else "usb",
                }
                for device_id, model in self.controller.get_devices()
            ]

        entries = []
        for item in raw_devices:
            device_id = item["device_id"]
            status = item.get("status", "device")
            model = item.get("model") or "未知设备"
            transport = item.get("transport") or ("wifi" if ":" in device_id else "usb")

            tags = []
            if status == "device":
                tags.append("WiFi" if transport == "wifi" else "USB")
            elif status == "offline":
                tags.append("离线")
            elif status == "unauthorized":
                tags.append("未授权")
            else:
                tags.append(status)

            if device_id in active_device_ids:
                tags.append("正在投屏")

            prefix = "★ " if device_id == last_connected_device_id else ""
            display_text = f"{prefix}{model} ({device_id}) [{' / '.join(tags)}]"

            entries.append({
                "device_id": device_id,
                "status": status,
                "model": model,
                "transport": transport,
                "display_text": display_text,
            })
        return entries

    def sync_device_widgets(self, primary_combo, secondary_combo=None, preferred_device_id=None,
                            active_device_ids=None, last_connected_device_id=None):
        """同步一个或两个设备下拉框，并恢复优先设备选择。"""
        devices = self.list_device_entries(
            active_device_ids=active_device_ids,
            last_connected_device_id=last_connected_device_id,
        )

        primary_combo.clear()
        if secondary_combo is not None:
            secondary_combo.clear()

        for item in devices:
            primary_combo.addItem(item["display_text"], item["device_id"])
            if secondary_combo is not None:
                secondary_combo.addItem(item["display_text"], item["device_id"])

        selected_id = self._restore_selection(primary_combo, secondary_combo, preferred_device_id)
        return devices, selected_id

    def _restore_selection(self, primary_combo, secondary_combo=None, preferred_device_id=None):
        """根据优先设备恢复选中项。"""
        if preferred_device_id:
            for index in range(primary_combo.count()):
                if primary_combo.itemData(index) == preferred_device_id:
                    primary_combo.setCurrentIndex(index)
                    if secondary_combo is not None:
                        secondary_combo.setCurrentIndex(index)
                    return preferred_device_id

        if primary_combo.count() > 0:
            primary_combo.setCurrentIndex(0)
            if secondary_combo is not None:
                secondary_combo.setCurrentIndex(0)
            return primary_combo.currentData()

        return None