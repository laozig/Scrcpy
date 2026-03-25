#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re

from runtime_helpers import build_scrcpy_command


class ScrcpyCommandService:
    """负责将界面选项转换为 scrcpy 命令。"""

    PRESETS = {
        "流畅模式": {
            "bit_rate": "4",
            "max_size": "720",
            "max_fps": "60",
            "video_codec": "默认",
            "fullscreen": False,
            "always_on_top": True,
            "show_touches": False,
            "turn_screen_off": False,
            "stay_awake": False,
            "record": False,
            "record_only": False,
        },
        "清晰模式": {
            "bit_rate": "12",
            "max_size": "1080",
            "max_fps": "30",
            "video_codec": "默认",
            "fullscreen": False,
            "always_on_top": True,
            "show_touches": False,
            "turn_screen_off": False,
            "stay_awake": False,
            "record": False,
            "record_only": False,
        },
        "录制模式": {
            "bit_rate": "8",
            "max_size": "1080",
            "max_fps": "30",
            "video_codec": "默认",
            "fullscreen": False,
            "always_on_top": False,
            "show_touches": False,
            "turn_screen_off": False,
            "stay_awake": True,
            "record": True,
            "record_only": True,
        },
        "低性能模式": {
            "bit_rate": "2",
            "max_size": "720",
            "max_fps": "24",
            "video_codec": "h264",
            "fullscreen": False,
            "always_on_top": False,
            "show_touches": False,
            "turn_screen_off": False,
            "stay_awake": False,
            "record": False,
            "record_only": False,
        },
    }

    def build_command_from_ui(self, ui, scrcpy_path, device_id, *, window_title, window_x=100, window_y=100):
        """从 UI 收集参数并构造 scrcpy 命令。"""
        bit_rate, error = self._parse_optional_int(ui.bitrate_input.text(), "比特率")
        if error:
            return None, error, False

        max_size, error = self._parse_optional_int(ui.maxsize_input.text(), "最大尺寸")
        if error:
            return None, error, False

        max_fps, error = self._parse_optional_int(ui.maxfps_input.text(), "帧率")
        if error:
            return None, error, False

        display_id, error = self._parse_optional_int(ui.displayid_input.text(), "显示ID")
        if error:
            return None, error, False

        crop, error = self._normalize_crop(ui.crop_input.text())
        if error:
            return None, error, False

        record_path, needs_warning = self._normalize_record_path(
            ui.record_cb.isChecked(),
            ui.record_path.text(),
            ui.format_combo.currentText(),
        )
        if needs_warning:
            return None, "请提供录制文件保存路径", True

        if ui.record_only_cb.isChecked() and not record_path:
            return None, "纯录制模式需要先提供录制文件保存路径", True

        codec = ui.codec_combo.currentText()
        if codec == "默认":
            codec = None

        command = build_scrcpy_command(
            scrcpy_path,
            device_id,
            bit_rate=bit_rate,
            max_size=max_size,
            max_fps=max_fps,
            record_path=record_path,
            fullscreen=ui.fullscreen_cb.isChecked(),
            always_on_top=ui.always_top_cb.isChecked(),
            show_touches=ui.show_touches_cb.isChecked(),
            no_control=ui.no_control_cb.isChecked(),
            disable_clipboard=ui.disable_clipboard_cb.isChecked(),
            rotation=ui.rotation_combo.currentText(),
            turn_screen_off=ui.turn_screen_off_cb.isChecked(),
            stay_awake=ui.stay_awake_cb.isChecked(),
            video_codec=codec,
            display_id=display_id,
            crop=crop,
            no_window=ui.record_only_cb.isChecked(),
            window_title=window_title,
            no_audio=True,
            window_x=window_x,
            window_y=window_y,
        )
        return command, None, False

    def apply_preset_to_ui(self, ui, preset_name):
        preset = self.PRESETS.get(preset_name)
        if not preset:
            return False

        ui.bitrate_input.setText(preset.get("bit_rate", ""))
        ui.maxsize_input.setText(preset.get("max_size", ""))
        ui.maxfps_input.setText(preset.get("max_fps", ""))

        codec = preset.get("video_codec", "默认")
        index = ui.codec_combo.findText(codec)
        if index >= 0:
            ui.codec_combo.setCurrentIndex(index)

        ui.fullscreen_cb.setChecked(bool(preset.get("fullscreen", False)))
        ui.always_top_cb.setChecked(bool(preset.get("always_on_top", False)))
        ui.show_touches_cb.setChecked(bool(preset.get("show_touches", False)))
        ui.turn_screen_off_cb.setChecked(bool(preset.get("turn_screen_off", False)))
        ui.stay_awake_cb.setChecked(bool(preset.get("stay_awake", False)))
        ui.record_cb.setChecked(bool(preset.get("record", False)))
        ui.record_only_cb.setChecked(bool(preset.get("record_only", False)))
        return True

    def _parse_optional_int(self, value, field_name):
        value = (value or "").strip()
        if not value:
            return None, None
        try:
            return int(value), None
        except ValueError:
            return None, f"错误: {field_name}必须是数字"

    def _normalize_record_path(self, enabled, record_path, record_format):
        if not enabled:
            return None, False

        record_file = (record_path or "").strip()
        if not record_file:
            return None, True

        if not record_file.endswith(f".{record_format}"):
            record_file = f"{record_file}.{record_format}"
        return record_file, False

    def _normalize_crop(self, crop_value):
        crop_value = (crop_value or "").strip()
        if not crop_value:
            return None, None
        if not re.match(r"^\d+:\d+:\d+:\d+$", crop_value):
            return None, "错误: 裁剪格式必须是 宽:高:X:Y"
        return crop_value, None