#!/usr/bin/env python
# -*- coding: utf-8 -*-

from utils import load_settings, save_settings


class ConfigService:
    """负责 Scrcpy GUI 配置的加载与保存。"""

    def __init__(self, config_path):
        self.config_path = config_path

    def load_into(self, ui):
        """将配置加载到 UI 控件。"""
        config = load_settings(self.config_path, default={})
        if not config:
            return

        if hasattr(ui, "runtime_path_overrides"):
            ui.runtime_path_overrides = {
                "adb_path": str(config.get("adb_path", "") or "").strip(),
                "scrcpy_path": str(config.get("scrcpy_path", "") or "").strip(),
                "scrcpy_server_path": str(config.get("scrcpy_server_path", "") or "").strip(),
            }

        ui.screenshot_dir = config.get("screenshot_dir", "")
        ui.device_profiles = config.get("device_profiles", {})
        ui.pending_selected_device = config.get("selected_device") or config.get("device_id")
        ui.last_connected_device = config.get("last_connected_device")

        bit_rate = config.get("bit_rate")
        if bit_rate:
            ui.bitrate_input.setText(str(bit_rate).rstrip("M"))

        max_size = config.get("max_size") or config.get("max_resolution")
        if not max_size:
            resolution = config.get("resolution")
            if resolution:
                max_size = str(resolution).split(":", 1)[0]
        if max_size:
            ui.maxsize_input.setText(str(max_size))

        record_path = config.get("record_path")
        if record_path:
            ui.record_path.setText(record_path)

        record_format = config.get("record_format") or config.get("format")
        if record_format:
            index = ui.format_combo.findText(str(record_format))
            if index >= 0:
                ui.format_combo.setCurrentIndex(index)

        rotation = config.get("rotation")
        if rotation:
            index = ui.rotation_combo.findText(str(rotation))
            if index >= 0:
                ui.rotation_combo.setCurrentIndex(index)

        ui.record_cb.setChecked(False)
        ui.fullscreen_cb.setChecked(bool(config.get("fullscreen", False)))
        ui.always_top_cb.setChecked(bool(config.get("always_on_top", False)))
        ui.show_touches_cb.setChecked(bool(config.get("show_touches", False)))
        ui.no_control_cb.setChecked(bool(config.get("no_control", False)))
        ui.disable_clipboard_cb.setChecked(bool(config.get("disable_clipboard", False)))
        ui.auto_refresh_cb.setChecked(bool(config.get("auto_refresh", False)))

        ui.maxfps_input.setText(str(config.get("max_fps", "")))
        ui.displayid_input.setText(str(config.get("display_id", "")) if config.get("display_id") not in (None, "") else "")
        ui.crop_input.setText(str(config.get("crop", "") or ""))

        codec = config.get("video_codec") or "默认"
        index = ui.codec_combo.findText(str(codec))
        if index >= 0:
            ui.codec_combo.setCurrentIndex(index)

        ui.turn_screen_off_cb.setChecked(bool(config.get("turn_screen_off", False)))
        ui.stay_awake_cb.setChecked(bool(config.get("stay_awake", False)))
        ui.record_only_cb.setChecked(False)

        preset = config.get("preset")
        if preset:
            index = ui.preset_combo.findText(str(preset))
            if index >= 0:
                ui.preset_combo.setCurrentIndex(index)

        if hasattr(ui, "quick_screenshot_mode_action"):
            ui.quick_screenshot_mode_action.setChecked(bool(config.get("quick_screenshot_enabled", False)))
        if hasattr(ui, "screenshot_date_archive_action"):
            ui.screenshot_date_archive_action.setChecked(bool(config.get("screenshot_date_archive", False)))
        if hasattr(ui, "connect_only_new_action"):
            ui.connect_only_new_action.setChecked(bool(config.get("connect_only_new", True)))
        if hasattr(ui, "window_layout_action_group"):
            layout_mode = config.get("window_layout_mode", "网格排布")
            for action in ui.window_layout_action_group.actions():
                if action.text() == layout_mode:
                    action.setChecked(True)
                    break
        if hasattr(ui, "open_record_dir_action"):
            ui.open_record_dir_action.setChecked(bool(config.get("open_record_dir_on_finish", False)))
        if hasattr(ui, "open_record_file_action"):
            ui.open_record_file_action.setChecked(bool(config.get("open_record_file_on_finish", False)))

    def load_runtime_paths(self):
        """单独加载运行时依赖路径配置。"""
        config = load_settings(self.config_path, default={})
        return {
            "adb_path": str(config.get("adb_path", "") or "").strip(),
            "scrcpy_path": str(config.get("scrcpy_path", "") or "").strip(),
            "scrcpy_server_path": str(config.get("scrcpy_server_path", "") or "").strip(),
        }

    def save_from(self, ui):
        """从 UI 控件收集配置并保存。"""
        runtime_paths = getattr(ui, "runtime_path_overrides", {}) or {}
        config = {
            "adb_path": str(runtime_paths.get("adb_path", "") or "").strip(),
            "scrcpy_path": str(runtime_paths.get("scrcpy_path", "") or "").strip(),
            "scrcpy_server_path": str(runtime_paths.get("scrcpy_server_path", "") or "").strip(),
            "screenshot_dir": getattr(ui, "screenshot_dir", ""),
            "quick_screenshot_enabled": bool(getattr(getattr(ui, "quick_screenshot_mode_action", None), "isChecked", lambda: False)()),
            "screenshot_date_archive": bool(getattr(getattr(ui, "screenshot_date_archive_action", None), "isChecked", lambda: False)()),
            "connect_only_new": bool(getattr(getattr(ui, "connect_only_new_action", None), "isChecked", lambda: True)()),
            "window_layout_mode": getattr(ui, "get_window_layout_mode", lambda: "网格排布")(),
            "open_record_dir_on_finish": bool(getattr(getattr(ui, "open_record_dir_action", None), "isChecked", lambda: False)()),
            "open_record_file_on_finish": bool(getattr(getattr(ui, "open_record_file_action", None), "isChecked", lambda: False)()),
            "selected_device": ui.device_combo.currentData() if ui.device_combo.count() else ui.pending_selected_device,
            "device_id": ui.device_combo.currentData() if ui.device_combo.count() else ui.pending_selected_device,
            "last_connected_device": getattr(ui, "last_connected_device", None),
            "device_profiles": getattr(ui, "device_profiles", {}),
            "bit_rate": ui.bitrate_input.text().strip(),
            "max_size": ui.maxsize_input.text().strip(),
            "max_resolution": ui.maxsize_input.text().strip(),
            "max_fps": ui.maxfps_input.text().strip(),
            "display_id": ui.displayid_input.text().strip(),
            "crop": ui.crop_input.text().strip(),
            "record": ui.record_cb.isChecked(),
            "record_path": ui.record_path.text().strip(),
            "record_format": ui.format_combo.currentText(),
            "format": ui.format_combo.currentText(),
            "video_codec": ui.codec_combo.currentText(),
            "rotation": ui.rotation_combo.currentText(),
            "turn_screen_off": ui.turn_screen_off_cb.isChecked(),
            "stay_awake": ui.stay_awake_cb.isChecked(),
            "record_only": ui.record_only_cb.isChecked(),
            "preset": ui.preset_combo.currentText(),
            "fullscreen": ui.fullscreen_cb.isChecked(),
            "always_on_top": ui.always_top_cb.isChecked(),
            "show_touches": ui.show_touches_cb.isChecked(),
            "no_control": ui.no_control_cb.isChecked(),
            "disable_clipboard": ui.disable_clipboard_cb.isChecked(),
            "auto_refresh": ui.auto_refresh_cb.isChecked(),
        }
        save_settings(config, self.config_path)

    def collect_device_profile(self, ui):
        """收集当前设备专属参数配置。"""
        return {
            "bit_rate": ui.bitrate_input.text().strip(),
            "max_size": ui.maxsize_input.text().strip(),
            "max_fps": ui.maxfps_input.text().strip(),
            "record": ui.record_cb.isChecked(),
            "record_path": ui.record_path.text().strip(),
            "record_format": ui.format_combo.currentText(),
            "video_codec": ui.codec_combo.currentText(),
            "display_id": ui.displayid_input.text().strip(),
            "crop": ui.crop_input.text().strip(),
            "rotation": ui.rotation_combo.currentText(),
            "turn_screen_off": ui.turn_screen_off_cb.isChecked(),
            "stay_awake": ui.stay_awake_cb.isChecked(),
            "record_only": ui.record_only_cb.isChecked(),
            "fullscreen": ui.fullscreen_cb.isChecked(),
            "always_on_top": ui.always_top_cb.isChecked(),
            "show_touches": ui.show_touches_cb.isChecked(),
            "no_control": ui.no_control_cb.isChecked(),
            "disable_clipboard": ui.disable_clipboard_cb.isChecked(),
            "preset": ui.preset_combo.currentText(),
        }

    def apply_device_profile(self, ui, profile):
        """把设备专属参数应用到界面。"""
        profile = profile or {}
        ui.bitrate_input.setText(str(profile.get("bit_rate", "")))
        ui.maxsize_input.setText(str(profile.get("max_size", "")))
        ui.maxfps_input.setText(str(profile.get("max_fps", "")))
        ui.record_cb.setChecked(False)
        ui.record_path.setText(str(profile.get("record_path", "") or ""))

        record_format = profile.get("record_format") or "mp4"
        index = ui.format_combo.findText(str(record_format))
        if index >= 0:
            ui.format_combo.setCurrentIndex(index)

        video_codec = profile.get("video_codec") or "默认"
        index = ui.codec_combo.findText(str(video_codec))
        if index >= 0:
            ui.codec_combo.setCurrentIndex(index)

        ui.displayid_input.setText(str(profile.get("display_id", "") or ""))
        ui.crop_input.setText(str(profile.get("crop", "") or ""))

        rotation = profile.get("rotation") or "不限制"
        index = ui.rotation_combo.findText(str(rotation))
        if index >= 0:
            ui.rotation_combo.setCurrentIndex(index)

        ui.turn_screen_off_cb.setChecked(bool(profile.get("turn_screen_off", False)))
        ui.stay_awake_cb.setChecked(bool(profile.get("stay_awake", False)))
        ui.record_only_cb.setChecked(False)
        ui.fullscreen_cb.setChecked(bool(profile.get("fullscreen", False)))
        ui.always_top_cb.setChecked(bool(profile.get("always_on_top", False)))
        ui.show_touches_cb.setChecked(bool(profile.get("show_touches", False)))
        ui.no_control_cb.setChecked(bool(profile.get("no_control", False)))
        ui.disable_clipboard_cb.setChecked(bool(profile.get("disable_clipboard", False)))

        preset = profile.get("preset") or "自定义"
        index = ui.preset_combo.findText(str(preset))
        if index >= 0:
            ui.preset_combo.setCurrentIndex(index)