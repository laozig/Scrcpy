#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys

from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import QMessageBox

from app_manager import AppManagerDialog
from utils import console_log


class UISupportService:
    """封装主界面里较零散的 UI 辅助逻辑。"""

    def set_window_icon(self, window):
        """为窗口设置图标。"""
        try:
            try:
                import create_icon

                icon_bytes = create_icon.get_icon_bytes()
                if icon_bytes:
                    pixmap = QPixmap()
                    pixmap.loadFromData(icon_bytes)
                    if not pixmap.isNull():
                        window.setWindowIcon(QIcon(pixmap))
                        console_log("已设置内嵌图标")
                        return
            except Exception as e:
                console_log(f"无法加载内嵌图标: {e}", "WARN")

            for icon_path in self._icon_candidates():
                if os.path.exists(icon_path):
                    try:
                        app_icon = QIcon(icon_path)
                        if not app_icon.isNull():
                            window.setWindowIcon(app_icon)
                            console_log(f"已设置窗口图标: {icon_path}")
                            return
                    except Exception as e:
                        console_log(f"加载图标失败: {e}", "WARN")

            console_log("没有找到有效的图标文件", "WARN")

            try:
                import create_icon

                create_icon.create_simple_icon()
                app_icon = QIcon("1.ico")
                window.setWindowIcon(app_icon)
                console_log("已设置新生成的图标")
            except Exception as e:
                console_log(f"生成图标失败: {e}", "ERROR")
        except Exception as e:
            console_log(f"设置图标过程中出错: {e}", "ERROR")

    def set_application_icon(self, app):
        """为 QApplication 设置应用图标。"""
        icon_path = ""
        for path in self._icon_candidates():
            if os.path.exists(path):
                icon_path = path
                break

        if icon_path:
            try:
                app_icon = QIcon(icon_path)
                if not app_icon.isNull():
                    app.setWindowIcon(app_icon)
                    console_log(f"已设置应用程序图标: {icon_path}")
            except Exception as e:
                console_log(f"应用程序图标设置失败: {e}", "WARN")

    def show_about(self, parent):
        """显示关于对话框。"""
        about_text = "Scrcpy GUI\n\n"
        about_text += "一个基于scrcpy的Android设备镜像和控制工具。\n\n"
        about_text += "支持多设备连接、WIFI连接、屏幕录制等功能。\n"
        about_text += "支持截图功能。\n\n"
        QMessageBox.about(parent, "关于Scrcpy GUI", about_text)

    def show_app_manager(self, parent, controller, device_id=None):
        """显示应用管理器对话框。"""
        app_manager = AppManagerDialog(parent, controller, initial_device_id=device_id)
        app_manager.exec_()

    def _icon_candidates(self):
        return [
            "1.ico",
            os.path.join(os.getcwd(), "1.ico"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "1.ico"),
            os.path.join(os.path.dirname(sys.executable), "1.ico"),
        ]