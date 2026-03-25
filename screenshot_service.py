#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import os
import re

from PyQt5.QtWidgets import QFileDialog, QMessageBox

from utils import open_path


class ScreenshotService:
    """负责单设备截图与批量截图逻辑。"""

    def __init__(self, owner, controller):
        self.owner = owner
        self.controller = controller

    def take_screenshot(self):
        """截取当前选中设备屏幕并保存到电脑。"""
        if hasattr(self.owner, 'quick_screenshot_mode_action') and self.owner.quick_screenshot_mode_action.isChecked():
            self.quick_save_screenshot()
            return

        if self.owner.device_combo.currentIndex() < 0:
            if hasattr(self.owner, '_show_device_selection_hint'):
                self.owner._show_device_selection_hint("截图")
            else:
                QMessageBox.information(self.owner, "提示", "请先选择一个设备后再执行“截图”")
            return

        device_id = self.owner.device_combo.currentData()
        if not device_id:
            if hasattr(self.owner, 'show_warning_message'):
                self.owner.show_warning_message("警告", "当前设备ID无效，请刷新设备列表后重试", show_dialog=True)
            else:
                self.owner.log("当前设备ID无效，请刷新设备列表后重试")
                QMessageBox.warning(self.owner, "警告", "当前设备ID无效，请刷新设备列表后重试")
            return

        device_model = self._find_device_model(device_id)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"screenshot_{device_model}_{timestamp}.png"

        filename, _ = QFileDialog.getSaveFileName(
            self.owner,
            "保存截图",
            default_filename,
            "图片文件 (*.png)",
        )
        if not filename:
            return

        success, message = self.controller.capture_screenshot(device_id, filename)
        if success:
            self.owner.log(f"设备 {device_model} ({device_id}) 截图已保存至 {filename}")
            if hasattr(self.owner, 'show_info_message'):
                self.owner.show_info_message("截图完成", f"截图已保存：{filename}", show_dialog=False, duration=2500)
            if hasattr(self.owner, 'ask_confirmation'):
                reply = self.owner.ask_confirmation("查看截图", "截图已保存，是否立即查看？", default=QMessageBox.No)
            else:
                reply = QMessageBox.question(
                    self.owner,
                    "查看截图",
                    "截图已保存，是否立即查看？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
            if reply == QMessageBox.Yes:
                self._open_path(filename)
        else:
            self.owner.log(f"截图失败: {message}")

    def quick_save_screenshot(self):
        """快速截图到默认目录。"""
        device_id = self.owner.device_combo.currentData() if self.owner.device_combo.currentIndex() >= 0 else None
        if not device_id:
            if hasattr(self.owner, '_show_device_selection_hint'):
                self.owner._show_device_selection_hint("快速截图")
            return

        device_model = self._find_device_model(device_id)
        target_dir = self._ensure_screenshot_base_dir(device_model)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(target_dir, f"{timestamp}.png")

        success, message = self.controller.capture_screenshot(device_id, filename)
        if success:
            self.owner.log(f"快速截图已保存: {filename}")
            if hasattr(self.owner, 'show_info_message'):
                self.owner.show_info_message("快速截图", f"已保存到 {filename}", show_dialog=False, duration=2500)
        else:
            self.owner.log(f"快速截图失败: {message}")

    def _find_device_model(self, device_id):
        if hasattr(self.owner, '_get_selected_device_model') and self.owner.device_combo.currentData() == device_id:
            return self._sanitize_name(self.owner._get_selected_device_model())
        for index in range(self.owner.device_combo.count()):
            if device_id in self.owner.device_combo.itemText(index):
                raw = self.owner.device_combo.itemText(index).split(" (")[0]
                return self._sanitize_name(raw)
        return "未知设备"

    def _ensure_screenshot_base_dir(self, device_model, base_dir=None):
        root_dir = base_dir or getattr(self.owner, 'screenshot_dir', '')
        if not root_dir:
            root_dir = os.path.join(os.path.expanduser("~"), "Pictures", "ScrcpyGUI")
            self.owner.screenshot_dir = root_dir

        safe_name = self._sanitize_name(device_model)
        if hasattr(self.owner, 'screenshot_date_archive_action') and self.owner.screenshot_date_archive_action.isChecked():
            date_folder = datetime.datetime.now().strftime("%Y-%m-%d")
            target_dir = os.path.join(root_dir, date_folder, safe_name)
        else:
            target_dir = os.path.join(root_dir, safe_name)
        os.makedirs(target_dir, exist_ok=True)
        return target_dir

    def _sanitize_name(self, text):
        text = (text or "未知设备").replace("★", "").strip()
        text = re.sub(r'\s*\[[^\]]+\]\s*$', '', text)
        text = re.sub(r'[\\/:*?"<>|]+', '_', text)
        return text.strip() or "未知设备"

    def _open_path(self, path):
        return open_path(path)