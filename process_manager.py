#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt5.QtCore import QProcess

from utils import console_log


class ProcessManager:
    """统一管理主界面的 QProcess 生命周期。"""

    def __init__(self, owner):
        self.owner = owner
        self.device_processes = {}
        self.control_bars = {}
        self.process_tracking = []

    def track_process(self, process):
        """跟踪 QProcess 生命周期，避免对象过早释放。"""
        if process not in self.process_tracking:
            self.process_tracking.append(process)
        process.finished.connect(lambda *_args, proc=process: self.cleanup_tracked_process(proc))
        return process

    def cleanup_tracked_process(self, process):
        """清理已结束的临时进程引用。"""
        try:
            if process in self.process_tracking:
                self.process_tracking.remove(process)
        except ValueError:
            pass
        try:
            if process.parent() is self.owner and process not in self.device_processes.values():
                process.deleteLater()
        except (RuntimeError, ReferenceError):
            pass

    def launch_device_process(self, device_id, command, success_message=None):
        """启动并跟踪单个设备的 scrcpy 进程。"""
        process = self.track_process(QProcess(self.owner))
        process.readyReadStandardOutput.connect(lambda proc=process, dev=device_id: self.owner.handle_process_output(proc, dev))
        process.readyReadStandardError.connect(lambda proc=process, dev=device_id: self.owner.handle_process_error(proc, dev))
        process.finished.connect(self.owner.create_process_finished_handler(device_id))
        self.device_processes[device_id] = process
        process.start(command[0], command[1:])
        if success_message:
            self.owner.log(success_message)
        return process

    def stop_device_process(self, device_id, timeout_ms=2000):
        """停止单个设备对应的进程。"""
        if device_id not in self.device_processes:
            return False

        process = self.device_processes[device_id]
        if process.state() != QProcess.Running:
            self.device_processes.pop(device_id, None)
            return False

        self.owner.log(f"正在停止设备 {device_id} 的 scrcpy 进程...")
        process.terminate()
        if not process.waitForFinished(timeout_ms):
            process.kill()
        self.device_processes.pop(device_id, None)
        self.owner.log(f"已停止设备 {device_id} 的 scrcpy 进程")
        return True

    def stop_all_processes(self, timeout_ms=2000):
        """集中终止当前已知的所有 QProcess 实例。"""
        for device_id, process in list(self.device_processes.items()):
            try:
                if process and process.state() == QProcess.Running:
                    console_log(f"正在终止设备 {device_id} 的进程...")
                    try:
                        process.disconnect()
                    except (TypeError, RuntimeError):
                        pass
                    process.kill()
                    process.waitForFinished(timeout_ms)
                    console_log(f"已终止设备 {device_id} 的进程")
            except Exception as e:
                console_log(f"终止设备 {device_id} 进程时出错: {e}", "ERROR")
        self.device_processes.clear()

        for i, proc in enumerate(list(self.process_tracking)):
            try:
                if proc and proc.state() == QProcess.Running:
                    proc.disconnect()
                    proc.kill()
                    proc.waitForFinished(timeout_ms)
                    console_log(f"已终止跟踪进程#{i}")
            except Exception as e:
                console_log(f"终止跟踪进程 #{i} 时出错: {e}", "ERROR")
        self.process_tracking.clear()

    def cleanup_before_exit(self, main_process=None, event_monitor=None, timeout_ms=2000):
        """在应用退出前统一清理资源。"""
        try:
            self.owner.is_closing = True
            console_log("开始清理进程...")

            if event_monitor:
                try:
                    event_monitor.stop_monitoring()
                    console_log("停止事件监控成功")
                except Exception as e:
                    console_log(f"停止事件监控时出错: {e}", "ERROR")

            for device_id, control_bar in list(self.control_bars.items()):
                try:
                    if control_bar is not None:
                        control_bar.deleteLater()
                    console_log(f"已删除设备 {device_id} 的控制栏")
                except Exception as e:
                    console_log(f"删除控制栏时出错: {e}", "ERROR")
            self.control_bars.clear()

            self.stop_all_processes(timeout_ms)

            if main_process and main_process.state() == QProcess.Running:
                try:
                    main_process.disconnect()
                    main_process.kill()
                    main_process.waitForFinished(1000)
                except Exception as e:
                    console_log(f"终止主进程时出错: {e}", "ERROR")

            console_log("所有进程已清理完毕")
        except Exception as e:
            console_log(f"清理进程时出错: {e}", "ERROR")