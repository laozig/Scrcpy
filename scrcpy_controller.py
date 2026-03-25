#!/usr/bin/env python
# -*- coding: utf-8 -*-

import subprocess
import shlex
import os
import re
import platform
import threading
import time
import random

from utils import console_log

"""
Scrcpy控制器模块，用于与Android设备进行通信和控制。

修复了以下问题：
1. 修复了execute_adb_command方法中的设备ID处理：确保正确传递设备ID参数
2. 改进了命令执行逻辑：将check参数设为False，以便捕获错误但继续执行
3. 添加了更详细的错误处理：添加了返回码检查和错误输出处理
4. 改进了日志输出：添加了更多的调试信息，方便排查问题
"""

class ScrcpyController:
    def __init__(self, adb_path="adb", scrcpy_path="scrcpy"):
        self.process = None
        self.system = platform.system()
        self.adb_path = adb_path or "adb"
        self.scrcpy_path = scrcpy_path or "scrcpy"

    def _adb_command(self, *args, device_id=None):
        """构建统一的 adb 命令。"""
        cmd = [self.adb_path]
        if device_id:
            cmd.extend(["-s", device_id])
        cmd.extend(args)
        return cmd

    def _scrcpy_command(self, *args):
        """构建统一的 scrcpy 命令。"""
        return [self.scrcpy_path, *args]
        
    def get_devices(self):
        """
        调用 adb devices 命令获取已连接的安卓设备列表
        
        Returns:
            list: 设备列表，每个元素为(device_id, model)的元组
        """
        try:
            return [
                (entry["device_id"], entry["model"])
                for entry in self.get_device_statuses()
                if entry.get("status") == "device"
            ]
        except Exception as e:
            console_log(f"获取设备列表出错: {e}", "ERROR")
            return []

    def get_device_statuses(self):
        """获取设备列表及状态信息。"""
        try:
            kwargs = {}
            if self.system == 'Windows':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

            result = subprocess.run(
                self._adb_command("devices", "-l"),
                capture_output=True,
                text=True,
                check=False,
                **kwargs
            )

            if result.returncode != 0:
                console_log(f"获取设备状态失败: {result.stderr}", "ERROR")
                return []

            devices = []
            lines = result.stdout.strip().split('\n')
            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue

                parts = line.split()
                if len(parts) < 2:
                    continue

                device_id = parts[0].strip()
                status = parts[1].strip()
                attrs = parts[2:]

                model = self._extract_attr(attrs, "model")
                transport = "wifi" if ":" in device_id else "usb"

                if status == "device":
                    if not model:
                        model = self._get_device_model(device_id)
                elif status == "offline":
                    model = model or "离线设备"
                elif status == "unauthorized":
                    model = model or "未授权设备"
                else:
                    model = model or "未知设备"

                devices.append({
                    "device_id": device_id,
                    "status": status,
                    "model": model or "未知设备",
                    "transport": transport,
                })

            return devices
        except Exception as e:
            console_log(f"获取设备状态出错: {e}", "ERROR")
            return []

    def _extract_attr(self, attrs, key):
        prefix = f"{key}:"
        for item in attrs:
            if item.startswith(prefix):
                return item[len(prefix):]
        return ""

    def _get_device_model(self, device_id):
        try:
            kwargs = {}
            if self.system == 'Windows':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

            model_result = subprocess.run(
                self._adb_command("shell", "getprop", "ro.product.model", device_id=device_id),
                capture_output=True,
                text=True,
                check=False,
                timeout=2,
                **kwargs
            )
            if model_result.returncode == 0:
                model = model_result.stdout.strip()
                if model:
                    return model
        except Exception as e:
            console_log(f"获取设备型号失败: {e}", "WARN")
            pass
        return "未知设备"
            
    def build_command(self, device_id=None, resolution=None, bit_rate=None, 
                      max_fps=None, record_path=None, fullscreen=False, 
                      no_control=False, disable_clipboard=False,
                      window_title=None, always_on_top=False):
        """
        根据传入参数构建scrcpy命令
        
        Args:
            device_id (str): 设备ID
            resolution (str): 分辨率，格式如 "1280:720" 或 "1280"
            bit_rate (str): 码率，如 "8M"
            max_fps (str): 帧率，如 "60"
            record_path (str): 录屏文件保存路径
            fullscreen (bool): 是否全屏显示
            no_control (bool): 是否禁用控制
            disable_clipboard (bool): 是否禁用剪贴板同步
            window_title (str): 窗口标题
            always_on_top (bool): 是否窗口置顶
            
        Returns:
            list: scrcpy命令参数列表
        """
        cmd = [self.scrcpy_path]
        
        # 设备ID
        if device_id:
            cmd.extend(["-s", device_id])
            
        # 分辨率 - 根据scrcpy文档，只提供一个数值即可限制最大尺寸
        if resolution:
            if ":" in resolution:
                # 如果提供的是宽:高格式，取宽度作为限制
                width = resolution.split(":")[0]
                cmd.append(f"--max-size={width}")
            else:
                cmd.append(f"--max-size={resolution}")
            
        # 码率
        if bit_rate:
            cmd.append(f"--video-bit-rate={bit_rate}")
            
        # 帧率
        if max_fps:
            cmd.append(f"--max-fps={max_fps}")
            
        # 录屏
        if record_path:
            cmd.append(f"--record={record_path}")
            
        # 全屏
        if fullscreen:
            cmd.append("--fullscreen")
            
        # 禁用控制
        if no_control:
            cmd.append("--no-control")
            
        # 禁用剪贴板同步
        if disable_clipboard:
            cmd.append("--no-clipboard-autosync")
            
        # 窗口标题
        if window_title:
            cmd.append(f"--window-title={window_title}")
            
        # 窗口置顶
        if always_on_top:
            cmd.append("--always-on-top")
            
        return cmd
            
    def run_scrcpy(self, command, log_callback=None):
        """
        使用subprocess运行scrcpy命令，并实时获取输出
        
        Args:
            command (list): scrcpy命令参数列表
            log_callback (function): 处理输出行的回调函数
            
        Returns:
            tuple: (成功标志, 信息)
        """
        # 调用更通用的execute_scrcpy_command方法
        return self.execute_scrcpy_command(command, log_callback)
            
    def stop_scrcpy(self):
        """停止scrcpy进程"""
        if self.process and self.process.poll() is None:
            try:
                if self.system == 'Windows':
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.process.pid)])
                else:
                    self.process.terminate()
                    self.process.wait(timeout=5)
                return True
            except Exception as e:
                console_log(f"停止进程错误: {e}", "ERROR")
                return False
        return True
        
    def check_dependencies(self):
        """检查scrcpy和adb是否已安装"""
        results = {}
        
        # 检查adb
        try:
            kwargs = {}
            if self.system == 'Windows':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                
            adb_version = subprocess.run(
                self._adb_command("version"), 
                capture_output=True, 
                text=True,
                **kwargs
            )
            results["adb"] = True
            match = re.search(r'Android Debug Bridge version ([\d\.]+)', adb_version.stdout)
            if match:
                results["adb_version"] = match.group(1)
            else:
                results["adb_version"] = "未知"
        except Exception as e:
            results["adb"] = False
            results["adb_version"] = None
            console_log(f"检查 adb 依赖失败: {e}", "WARN")
            
        # 检查scrcpy
        try:
            kwargs = {}
            if self.system == 'Windows':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                
            scrcpy_version = subprocess.run(
                self._scrcpy_command("--version"), 
                capture_output=True, 
                text=True,
                **kwargs
            )
            results["scrcpy"] = True
            match = re.search(r'scrcpy ([\d\.]+)', scrcpy_version.stdout)
            if match:
                results["scrcpy_version"] = match.group(1)
            else:
                results["scrcpy_version"] = "未知"
        except Exception as e:
            results["scrcpy"] = False
            results["scrcpy_version"] = None
            console_log(f"检查 scrcpy 依赖失败: {e}", "WARN")
            
        return results
        
    def set_device_tcpip_mode(self, device_id, port=5555):
        """
        将设备设置为TCP/IP模式
        
        Args:
            device_id (str): 设备ID
            port (int): TCP端口，默认5555
            
        Returns:
            tuple: (成功标志, 信息)
        """
        try:
            cmd = self._adb_command("tcpip", str(port), device_id=device_id)
            
            kwargs = {}
            if self.system == 'Windows':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                **kwargs
            )
            
            if "error" in result.stdout.lower() or "error" in result.stderr.lower():
                return False, result.stdout + result.stderr
                
            return True, f"端口 {port}"
        except Exception as e:
            return False, str(e)
            
    def connect_to_device(self, ip_address, port=5555):
        """
        连接到无线设备
        
        Args:
            ip_address (str): 设备IP地址
            port (int): 端口，默认5555
            
        Returns:
            tuple: (成功标志, 信息)
        """
        try:
            connection_string = f"{ip_address}:{port}"
            
            kwargs = {}
            if self.system == 'Windows':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                
            result = subprocess.run(
                self._adb_command("connect", connection_string),
                capture_output=True,
                text=True,
                check=True,
                **kwargs
            )
            
            output = result.stdout + result.stderr
            
            # 检查是否连接成功
            if "connected" in output.lower() and "cannot" not in output.lower():
                return True, connection_string
            else:
                return False, output
        except Exception as e:
            return False, str(e)
            
    def disconnect_device(self, ip_address=None):
        """
        断开无线设备连接
        
        Args:
            ip_address (str, optional): 特定设备IP地址，如为None则断开所有
            
        Returns:
            tuple: (成功标志, 信息)
        """
        try:
            cmd = self._adb_command("disconnect")
            if ip_address:
                cmd.append(ip_address)
            
            kwargs = {}
            if self.system == 'Windows':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                **kwargs
            )
            
            return True, result.stdout
        except Exception as e:
            return False, str(e)
            
    def capture_screenshot(self, device_id=None, save_path=None):
        """
        使用adb捕获设备屏幕截图并保存为PNG文件
        
        Args:
            device_id (str, optional): 设备ID，如果为None则使用当前连接的设备
            save_path (str, optional): 保存路径，如果为None则自动生成文件名
            
        Returns:
            tuple: (成功标志, 截图路径或错误信息)
        """
        try:
            # 如果未指定保存路径，则生成一个基于当前时间的文件名
            if not save_path:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                save_path = os.path.join(os.path.expanduser("~"), f"scrcpy_screenshot_{timestamp}.png")
                
            # 确保目录存在
            save_dir = os.path.dirname(save_path)
            if save_dir and not os.path.exists(save_dir):
                os.makedirs(save_dir)
                
            # 构建adb命令
            cmd = self._adb_command("exec-out", "screencap", "-p", device_id=device_id)
            
            # 执行命令并将输出重定向到文件
            kwargs = {}
            if self.system == 'Windows':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                
            with open(save_path, "wb") as f:
                subprocess.run(cmd, stdout=f, check=True, **kwargs)
                
            return True, save_path
        except Exception as e:
            return False, str(e)
    
    def get_device_info(self, device_id):
        """
        获取设备详细信息（型号、分辨率、安卓版本等）
        
        Args:
            device_id (str): 设备ID
            
        Returns:
            dict: 设备信息字典
        """
        info = {
            "model": "未知",
            "android_version": "未知",
            "resolution": "未知",
            "serial": device_id
        }
        
        if not device_id:
            return info
        
        kwargs = {}
        if self.system == 'Windows':
            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            
        try:
            # 获取设备型号
            model_cmd = self._adb_command("shell", "getprop", "ro.product.model", device_id=device_id)
            model_result = subprocess.run(model_cmd, capture_output=True, text=True, check=True, **kwargs)
            info["model"] = model_result.stdout.strip()
            
            # 获取安卓版本
            version_cmd = self._adb_command("shell", "getprop", "ro.build.version.release", device_id=device_id)
            version_result = subprocess.run(version_cmd, capture_output=True, text=True, check=True, **kwargs)
            info["android_version"] = version_result.stdout.strip()
            
            # 获取屏幕分辨率
            res_cmd = self._adb_command("shell", "wm", "size", device_id=device_id)
            res_result = subprocess.run(res_cmd, capture_output=True, text=True, check=True, **kwargs)
            res_output = res_result.stdout.strip()
            res_match = re.search(r'Physical size: (\d+x\d+)', res_output)
            if res_match:
                info["resolution"] = res_match.group(1)
                
            return info
        except Exception as e:
            console_log(f"获取设备信息出错: {e}", "ERROR")
            return info

    def execute_adb_command(self, command, device_id=None):
        """
        执行ADB命令
        
        Args:
            command (str or list): ADB命令，可以是字符串或列表
            device_id (str): 设备ID，默认为None
            
        Returns:
            tuple: (成功标志, 输出信息)
        """
        try:
            # 根据输入类型构建完整命令
            if isinstance(command, str):
                cmd_parts = shlex.split(command)
            else:
                cmd_parts = command

            # 构建完整命令
            full_cmd = [self.adb_path]
            
            # 如果指定了设备ID，则添加设备ID参数
            if device_id:
                full_cmd.extend(["-s", device_id])
                
            # 添加实际命令部分
            full_cmd.extend(cmd_parts)
            
            # Windows特殊处理，隐藏控制台窗口
            kwargs = {}
            if self.system == 'Windows':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                
            # 执行命令
            result = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                check=False,  # 不自动抛出异常
                **kwargs
            )
            
            # 检查返回码，非零表示可能出错
            if result.returncode != 0:
                error_output = result.stderr if result.stderr else result.stdout
                return False, f"命令失败(代码:{result.returncode}): {error_output}"
                
            return True, result.stdout
        except Exception as e:
            return False, str(e)

    def execute_scrcpy_command(self, command_args, log_callback=None):
        """
        执行scrcpy命令
        
        Args:
            command_args (list): scrcpy命令参数列表
            log_callback (function): 处理输出行的回调函数
            
        Returns:
            tuple: (成功标志, 信息)
        """
        try:
            # 确保命令是列表
            if isinstance(command_args, str):
                command_args = shlex.split(command_args)

            if not command_args:
                command_args = [self.scrcpy_path]
            elif os.path.basename(command_args[0]).lower() in ("scrcpy", "scrcpy.exe"):
                command_args[0] = self.scrcpy_path
            
            # 如果有正在运行的进程，先停止
            if self.process and self.process.poll() is None:
                self.stop_scrcpy()
                
            # Windows下需要设置creationflags以正确显示命令行窗口
            kwargs = {}
            if self.system == 'Windows':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            
            self.process = subprocess.Popen(
                command_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                **kwargs
            )
            
            # 如果有回调，开始读取输出
            if log_callback:
                def read_output():
                    for line in iter(self.process.stdout.readline, ''):
                        log_callback(line.strip())
                    self.process.stdout.close()
                
                output_thread = threading.Thread(target=read_output)
                output_thread.daemon = True
                output_thread.start()
                
            return True, " ".join(command_args)
        except Exception as e:
            return False, str(e)
            
    def get_device_brand(self, device_id):
        """
        获取设备品牌信息
        
        Args:
            device_id (str): 设备ID
            
        Returns:
            str: 设备品牌名称
        """
        try:
            kwargs = {}
            if self.system == 'Windows':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                
            cmd = self._adb_command("shell", "getprop", "ro.product.brand", device_id=device_id)
            result = subprocess.run(cmd, capture_output=True, text=True, check=False, **kwargs)
            if result.returncode == 0:
                return result.stdout.strip()
            return "未知品牌"
        except Exception as e:
            console_log(f"获取设备品牌失败: {e}", "WARN")
            return "未知品牌"
            
    def get_device_full_info(self, device_id):
        """
        获取设备的详细信息
        
        Args:
            device_id (str): 设备ID
            
        Returns:
            dict: 包含品牌、型号、Android版本等信息的字典
        """
        info = {
            "brand": "未知品牌",
            "model": "未知型号",
            "android": "未知版本",
            "id": device_id
        }
        
        if not device_id:
            return info
        
        kwargs = {}
        if self.system == 'Windows':
            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            
        try:
            # 获取品牌
            brand_cmd = self._adb_command("shell", "getprop", "ro.product.brand", device_id=device_id)
            brand_result = subprocess.run(brand_cmd, capture_output=True, text=True, check=False, **kwargs)
            if brand_result.returncode == 0:
                info["brand"] = brand_result.stdout.strip()
                
            # 获取型号
            model_cmd = self._adb_command("shell", "getprop", "ro.product.model", device_id=device_id)
            model_result = subprocess.run(model_cmd, capture_output=True, text=True, check=False, **kwargs)
            if model_result.returncode == 0:
                info["model"] = model_result.stdout.strip()
                
            # 获取Android版本
            android_cmd = self._adb_command("shell", "getprop", "ro.build.version.release", device_id=device_id)
            android_result = subprocess.run(android_cmd, capture_output=True, text=True, check=False, **kwargs)
            if android_result.returncode == 0:
                info["android"] = android_result.stdout.strip()
                
            return info
        except Exception as e:
            console_log(f"获取设备信息出错: {e}", "ERROR")
            return info

    # 添加群控相关方法
    def send_touch_event(self, device_id, x, y, action="tap"):
        """
        向设备发送触摸事件
        
        Args:
            device_id (str): 设备ID
            x (float/int 或 tuple): x坐标或(x1,y1,x2,y2)坐标元组
            y (float/int): y坐标
            action (str): 触摸类型 (tap, swipe, long等)
            
        Returns:
            bool: 是否成功
        """
        try:
            # 准备ADB命令
            cmd = self._adb_command("shell", device_id=device_id)
            
            if action == "tap":
                cmd.extend(["input", "tap", str(int(x)), str(int(y))])
            elif action == "swipe":
                # 检查x是否为元组(支持两种调用方式)
                if isinstance(x, tuple):
                    if len(x) == 4:  # 如果是(x1,y1,x2,y2)格式
                        x1, y1, x2, y2 = x
                    elif len(x) == 2:  # 如果是(x1,y1)格式，而y是(x2,y2)
                        x1, y1 = x
                        if isinstance(y, tuple) and len(y) == 2:
                            x2, y2 = y
                        else:
                            raise ValueError("缺少终点坐标")
                    else:
                        raise ValueError("坐标格式错误")
                else:  # 如果x,y是起始点，第二个点从参数中获取
                    if not isinstance(y, tuple) or len(y) != 2:
                        raise ValueError("缺少终点坐标")
                    x1, y1 = x, y[0]
                    x2, y2 = y[0], y[1]
                
                # 增加滑动持续时间，确保设备能识别滑动
                duration = 500  # 使用500ms，确保滑动能被识别
                cmd.extend(["input", "swipe", 
                           str(int(x1)), str(int(y1)), 
                           str(int(x2)), str(int(y2)),
                           str(duration)])
            elif action == "long":
                # 长按操作
                # Android中长按通常是使用swipe命令，起点和终点相同，持续时间长
                duration = 1000  # 长按持续1000ms (1秒)
                cmd.extend(["input", "swipe", 
                           str(int(x)), str(int(y)), 
                           str(int(x)), str(int(y)),
                           str(duration)])
                
            # 使用通用过程执行命令
            kwargs = {}
            if self.system == 'Windows':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                
            # 增加超时时间
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                **kwargs
            )
            
            # 等待命令完成，增加超时时间
            try:
                stdout, stderr = process.communicate(timeout=8)  # 8秒超时
                
                if process.returncode != 0:
                    console_log(f"触摸命令执行失败: {stderr}", "WARN")
                    return False
                    
                return True
            except subprocess.TimeoutExpired:
                process.kill()
                console_log("触摸命令执行超时", "WARN")
                return False
                
        except Exception as e:
            console_log(f"发送触摸事件失败: {str(e)}", "ERROR")
            return False
            
    def send_key_event(self, device_id, key_code):
        """
        向设备发送按键事件
        
        Args:
            device_id (str): 设备ID
            key_code (str/int): Android按键代码
            
        Returns:
            bool: 是否成功
        """
        try:
            cmd = self._adb_command("shell", "input", "keyevent", str(key_code), device_id=device_id)
            
            kwargs = {}
            if self.system == 'Windows':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                **kwargs
            )
            
            try:
                process.communicate(timeout=3)
                return True
            except subprocess.TimeoutExpired:
                process.kill()
                return False
                
        except Exception as e:
            console_log(f"发送按键事件到设备 {device_id} 失败: {e}", "ERROR")
            return False
            
    def send_text_input(self, device_id, text):
        """
        向设备发送文本输入
        
        Args:
            device_id (str): 设备ID
            text (str): 要输入的文本
            
        Returns:
            bool: 是否成功
        """
        try:
            # 对文本进行转义，确保命令行解析正确
            if self.system == 'Windows':
                # Windows下需要双引号
                escaped_text = f'"{text}"'
            else:
                # Linux/macOS下使用单引号
                escaped_text = f"'{text}'"
                
            cmd = self._adb_command("shell", "input", "text", escaped_text, device_id=device_id)
            
            kwargs = {}
            if self.system == 'Windows':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                **kwargs
            )
            
            try:
                process.communicate(timeout=3)
                return True
            except subprocess.TimeoutExpired:
                process.kill()
                return False
                
        except Exception as e:
            console_log(f"发送文本输入到设备 {device_id} 失败: {e}", "ERROR")
            return False
            
    def get_screen_size(self, device_id):
        """
        获取设备屏幕尺寸
        
        Args:
            device_id (str): 设备ID
            
        Returns:
            tuple: (宽, 高)，如果获取失败则返回None
        """
        try:
            cmd = self._adb_command("shell", "wm", "size", device_id=device_id)
            
            kwargs = {}
            if self.system == 'Windows':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                **kwargs
            )
            
            if result.returncode == 0:
                # 解析结果，如: Physical size: 1080x1920
                match = re.search(r'Physical size: (\d+)x(\d+)', result.stdout)
                if match:
                    width = int(match.group(1))
                    height = int(match.group(2))
                    return (width, height)
            
            return None
            
        except Exception as e:
            console_log(f"获取设备 {device_id} 屏幕尺寸失败: {e}", "ERROR")
            return None
            
    def sync_touch_from_main_to_slaves(self, main_device_id, slave_device_ids, x, y, action="tap"):
        """
        将主设备的触摸事件同步到从设备
        
        Args:
            main_device_id (str): 主控设备ID  
            slave_device_ids (list): 从设备ID列表
            x (float/int): x坐标或坐标元组
            y (float/int): y坐标或动作类型
            action (str): 触摸类型
            
        Returns:
            bool: 是否全部成功
        """
        if not slave_device_ids:
            return True
        
        # 记录开始时间
        start_time = time.time()
        console_log(f"开始同步操作 {action} 到 {len(slave_device_ids)} 个设备...")
            
        # 获取主设备分辨率
        main_size = self.get_screen_size(main_device_id)
        if not main_size:
            console_log(f"无法获取主设备 {main_device_id} 屏幕尺寸", "WARN")
            return False
            
        main_width, main_height = main_size
        
        # 获取主设备UI属性信息
        main_device_info = self.get_device_full_info(main_device_id)
        
        # 计算点击位置的相对比例
        if action == "tap" or action == "long":
            # 计算相对于屏幕的百分比位置
            x_ratio = x / main_width
            y_ratio = y / main_height
            
            # 保存实际坐标用于调试
            orig_x, orig_y = x, y
            
            # 计算屏幕区域（上、中、下，左、中、右）
            # 将屏幕划分为9个区域，便于不同尺寸设备间的映射
            x_zone = 0 if x_ratio < 0.33 else (2 if x_ratio > 0.66 else 1)
            y_zone = 0 if y_ratio < 0.33 else (2 if y_ratio > 0.66 else 1)
            screen_area = y_zone * 3 + x_zone  # 0-8的值表示9个区域
            
            zone_names = ["左上", "中上", "右上", "左中", "中心", "右中", "左下", "中下", "右下"]
            console_log(f"主设备点击区域: {zone_names[screen_area]}，坐标比例: ({x_ratio:.2f}, {y_ratio:.2f})")
            
        elif action == "swipe":
            # 处理滑动事件的坐标
            if isinstance(x, tuple):
                if len(x) == 4:
                    # 如果x是包含四个元素的元组，则认为是(x1,y1,x2,y2)
                    x1, y1, x2, y2 = x
                    x1_ratio = x1 / main_width
                    y1_ratio = y1 / main_height
                    x2_ratio = x2 / main_width
                    y2_ratio = y2 / main_height
                else:
                    # 兼容其他格式
                    try:
                        if isinstance(x, tuple) and len(x) == 2:
                            x1, y1 = x
                            if isinstance(y, tuple) and len(y) == 2:
                                x2, y2 = y
                            else:
                                # 如果y不是坐标元组，尝试从参数中解析
                                x2, y2 = y, action
                                action = "swipe"  # 确保动作类型正确
                        else:
                            console_log("不支持的滑动坐标格式", "WARN")
                            return False
                        
                        x1_ratio = x1 / main_width
                        y1_ratio = y1 / main_height
                        x2_ratio = x2 / main_width
                        y2_ratio = y2 / main_height
                    except Exception as e:
                        console_log(f"滑动坐标解析错误: {e}", "ERROR")
                        return False
            else:
                # 坐标格式错误
                console_log("滑动坐标格式错误", "WARN")
                return False
                
            # 获取滑动方向
            dx = x2_ratio - x1_ratio
            dy = y2_ratio - y1_ratio
            
            # 确定主要滑动方向
            if abs(dx) > abs(dy):
                # 水平滑动
                if dx > 0:
                    direction = "右"
                    strength = "强" if dx > 0.3 else "弱"
                else:
                    direction = "左"
                    strength = "强" if dx < -0.3 else "弱"
            else:
                # 垂直滑动
                if dy > 0:
                    direction = "下"
                    strength = "强" if dy > 0.3 else "弱"
                else:
                    direction = "上"
                    strength = "强" if dy < -0.3 else "弱"
                
            console_log(f"主设备滑动: {strength}{direction}滑，从({x1_ratio:.2f}, {y1_ratio:.2f})到({x2_ratio:.2f}, {y2_ratio:.2f})")
            
        # 所有成功执行的设备计数
        success_count = 0
        failed_devices = []
        
        # 获取主设备屏幕方向
        main_orientation = self.get_screen_orientation(main_device_id)
        
        # 等待一小段时间，确保主设备上的操作完全完成
        time.sleep(0.5)
        
        # 向每个从设备按顺序(而不是并行)发送触摸事件
        for device_idx, slave_id in enumerate(slave_device_ids):
            try:
                # 获取从设备分辨率
                slave_size = self.get_screen_size(slave_id)
                if not slave_size:
                    console_log(f"无法获取从设备 {slave_id} 屏幕尺寸", "WARN")
                    failed_devices.append(slave_id)
                    continue
                    
                slave_width, slave_height = slave_size
                
                # 获取从设备信息和屏幕方向
                slave_device_info = self.get_device_full_info(slave_id)
                slave_orientation = self.get_screen_orientation(slave_id)
                
                # 检查主设备和从设备方向是否一致
                orientation_consistent = (main_orientation == slave_orientation)
                if not orientation_consistent:
                    console_log(f"设备 {slave_id} 的屏幕方向({slave_orientation})与主设备({main_orientation})不一致", "WARN")
                
                # 将比例换算为目标设备上的像素坐标
                if action == "tap" or action == "long":
                    # 使用区域映射而非精确坐标转换
                    # 计算9个区域中心点的位置
                    zone_centers_x = [slave_width * 0.16, slave_width * 0.5, slave_width * 0.84]
                    zone_centers_y = [slave_height * 0.16, slave_height * 0.5, slave_height * 0.84]
                    
                    # 如果方向一致，使用更准确的映射
                    if orientation_consistent:
                        # 方向一致时，使用比例映射方式
                        target_x = int(x_ratio * slave_width)
                        target_y = int(y_ratio * slave_height)
                    else:
                        # 方向不一致时，使用区域映射
                        x_pos = 0 if x_ratio < 0.33 else (2 if x_ratio > 0.66 else 1)
                        y_pos = 0 if y_ratio < 0.33 else (2 if y_ratio > 0.66 else 1)
                        
                        # 根据屏幕方向旋转区域坐标
                        if (main_orientation == "portrait" and slave_orientation == "landscape") or \
                           (main_orientation == "landscape" and slave_orientation == "portrait"):
                            # 旋转90度 - 交换x和y
                            x_pos, y_pos = y_pos, 2 - x_pos
                            
                        target_x = int(zone_centers_x[x_pos])
                        target_y = int(zone_centers_y[y_pos])
                        
                    # 确保坐标在屏幕范围内
                    target_x = max(1, min(target_x, slave_width - 1))
                    target_y = max(1, min(target_y, slave_height - 1))
                    
                    # 添加少量随机偏移，避免完全相同的点击位置
                    target_x += random.randint(-5, 5)
                    target_y += random.randint(-5, 5)
                    
                    # 确保坐标在屏幕范围内
                    target_x = max(1, min(target_x, slave_width - 1))
                    target_y = max(1, min(target_y, slave_height - 1))
                    
                    console_log(f"同步{action}事件到设备{slave_id}: ({target_x}, {target_y}) [主设备比例: ({x_ratio:.2f}, {y_ratio:.2f})]")
                    
                    # 执行命令
                    if action == "tap":
                        result = self.send_touch_event(slave_id, target_x, target_y, "tap")
                    else:  # long press
                        result = self.send_touch_event(slave_id, target_x, target_y, "long")
                        
                elif action == "swipe":
                    # 滑动事件的坐标转换
                    if orientation_consistent:
                        # 方向一致，直接按比例转换
                        target_x1 = int(x1_ratio * slave_width)
                        target_y1 = int(y1_ratio * slave_height)
                        target_x2 = int(x2_ratio * slave_width)
                        target_y2 = int(y2_ratio * slave_height)
                    else:
                        # 方向不一致，使用方向感知的滑动
                        # 计算中心点
                        center_x = slave_width / 2
                        center_y = slave_height / 2
                        
                        # 根据主设备滑动方向确定从设备滑动方向
                        if direction == "右":
                            # 主设备向右滑动
                            if main_orientation == "portrait" and slave_orientation == "landscape":
                                # 从设备需要向下滑动
                                target_x1 = center_x
                                target_y1 = center_y - (slave_height * 0.3)
                                target_x2 = center_x
                                target_y2 = center_y + (slave_height * 0.3)
                            elif main_orientation == "landscape" and slave_orientation == "portrait":
                                # 从设备需要向右滑动
                                target_x1 = center_x - (slave_width * 0.3)
                                target_y1 = center_y
                                target_x2 = center_x + (slave_width * 0.3)
                                target_y2 = center_y
                            else:
                                # 相同方向
                                target_x1 = center_x - (slave_width * 0.3)
                                target_y1 = center_y
                                target_x2 = center_x + (slave_width * 0.3)
                                target_y2 = center_y
                        elif direction == "左":
                            # 主设备向左滑动
                            if main_orientation == "portrait" and slave_orientation == "landscape":
                                # 从设备需要向上滑动
                                target_x1 = center_x
                                target_y1 = center_y + (slave_height * 0.3)
                                target_x2 = center_x
                                target_y2 = center_y - (slave_height * 0.3)
                            elif main_orientation == "landscape" and slave_orientation == "portrait":
                                # 从设备需要向左滑动
                                target_x1 = center_x + (slave_width * 0.3)
                                target_y1 = center_y
                                target_x2 = center_x - (slave_width * 0.3)
                                target_y2 = center_y
                            else:
                                # 相同方向
                                target_x1 = center_x + (slave_width * 0.3)
                                target_y1 = center_y
                                target_x2 = center_x - (slave_width * 0.3)
                                target_y2 = center_y
                        elif direction == "上":
                            # 主设备向上滑动
                            if main_orientation == "portrait" and slave_orientation == "landscape":
                                # 从设备需要向左滑动
                                target_x1 = center_x + (slave_width * 0.3)
                                target_y1 = center_y
                                target_x2 = center_x - (slave_width * 0.3)
                                target_y2 = center_y
                            elif main_orientation == "landscape" and slave_orientation == "portrait":
                                # 从设备需要向上滑动
                                target_x1 = center_x
                                target_y1 = center_y + (slave_height * 0.3)
                                target_x2 = center_x
                                target_y2 = center_y - (slave_height * 0.3)
                            else:
                                # 相同方向
                                target_x1 = center_x
                                target_y1 = center_y + (slave_height * 0.3)
                                target_x2 = center_x
                                target_y2 = center_y - (slave_height * 0.3)
                        else:  # direction == "下"
                            # 主设备向下滑动
                            if main_orientation == "portrait" and slave_orientation == "landscape":
                                # 从设备需要向右滑动
                                target_x1 = center_x - (slave_width * 0.3)
                                target_y1 = center_y
                                target_x2 = center_x + (slave_width * 0.3)
                                target_y2 = center_y
                            elif main_orientation == "landscape" and slave_orientation == "portrait":
                                # 从设备需要向下滑动
                                target_x1 = center_x
                                target_y1 = center_y - (slave_height * 0.3)
                                target_x2 = center_x
                                target_y2 = center_y + (slave_height * 0.3)
                            else:
                                # 相同方向
                                target_x1 = center_x
                                target_y1 = center_y - (slave_height * 0.3)
                                target_x2 = center_x
                                target_y2 = center_y + (slave_height * 0.3)
                    
                    # 调整为整数坐标
                    target_x1 = int(target_x1)
                    target_y1 = int(target_y1)
                    target_x2 = int(target_x2)
                    target_y2 = int(target_y2)
                    
                    # 确保坐标在屏幕范围内
                    target_x1 = max(1, min(target_x1, slave_width - 1))
                    target_y1 = max(1, min(target_y1, slave_height - 1))
                    target_x2 = max(1, min(target_x2, slave_width - 1))
                    target_y2 = max(1, min(target_y2, slave_height - 1))
                    
                    # 添加小随机偏移
                    offset_x = random.randint(-10, 10)
                    offset_y = random.randint(-10, 10)
                    
                    target_x1 += offset_x
                    target_y1 += offset_y
                    target_x2 += offset_x
                    target_y2 += offset_y
                    
                    # 确保坐标在屏幕范围内
                    target_x1 = max(1, min(target_x1, slave_width - 1))
                    target_y1 = max(1, min(target_y1, slave_height - 1))
                    target_x2 = max(1, min(target_x2, slave_width - 1))
                    target_y2 = max(1, min(target_y2, slave_height - 1))
                    
                    console_log(f"同步滑动到设备{slave_id}: ({target_x1}, {target_y1}) -> ({target_x2}, {target_y2})")
                    
                    # 执行滑动命令
                    result = self.send_touch_event(
                        slave_id, 
                        (target_x1, target_y1, target_x2, target_y2), 
                        None,
                        "swipe"
                    )
                else:
                    console_log(f"未知的操作类型: {action}", "WARN")
                    result = False
                    
                if result:
                    success_count += 1
                else:
                    # 命令失败，记录失败设备
                    failed_devices.append(slave_id)
                    # 尝试智能重试
                    console_log(f"设备{slave_id}命令失败，尝试重试...", "WARN")
                    # 等待一小段时间后重试
                    time.sleep(1.0)
                    if action == "tap":
                        # 尝试点击屏幕附近位置
                        retry_x = target_x + random.randint(-15, 15)
                        retry_y = target_y + random.randint(-15, 15)
                        result = self.send_touch_event(slave_id, retry_x, retry_y, "tap")
                        if result:
                            console_log(f"设备{slave_id}重试成功: ({retry_x}, {retry_y})")
                            success_count += 1
                            failed_devices.remove(slave_id)
            except Exception as e:
                failed_devices.append(slave_id)
                console_log(f"同步操作到设备 {slave_id} 出错: {e}", "ERROR")
            
            # 每个设备操作后等待一小段时间，避免并发命令可能的问题
            if device_idx < len(slave_device_ids) - 1:
                time.sleep(0.5)
                
        # 计算总耗时
        elapsed_time = time.time() - start_time
        
        # 完整的结果报告
        if failed_devices:
            console_log(f"同步操作完成，耗时 {elapsed_time:.2f}秒，成功率: {success_count}/{len(slave_device_ids)}", "WARN")
            console_log(f"失败设备: {', '.join(failed_devices)}", "WARN")
            return False
        else:
            console_log(f"同步操作完成，耗时 {elapsed_time:.2f}秒，全部成功")
            return True
        
    def get_screen_orientation(self, device_id):
        """获取设备屏幕方向
        
        Args:
            device_id (str): 设备ID
            
        Returns:
            str: 'portrait'或'landscape'
        """
        try:
            kwargs = {}
            if self.system == 'Windows':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            result = subprocess.run(
                self._adb_command("shell", "dumpsys", "input", device_id=device_id),
                capture_output=True,
                text=True,
                check=False,
                timeout=3,
                **kwargs
            )
            output = result.stdout or ""
            
            # 检查输出中的方向信息
            if "SurfaceOrientation: 0" in output or "SurfaceOrientation: 2" in output:
                return "portrait"
            elif "SurfaceOrientation: 1" in output or "SurfaceOrientation: 3" in output:
                return "landscape"
            else:
                # 如果无法通过dumpsys判断，尝试通过分辨率判断
                size = self.get_screen_size(device_id)
                if size:
                    width, height = size
                    return "landscape" if width > height else "portrait"
                
                # 默认返回竖屏
                return "portrait"
                
        except Exception as e:
            console_log(f"获取设备 {device_id} 屏幕方向失败: {e}", "ERROR")
            return "portrait"  # 默认返回竖屏方向

    def create_sync_control_bridge(self, main_device_id, slave_device_ids):
        """
        建立主控设备和从设备之间的控制桥接
        
        Args:
            main_device_id (str): 主控设备ID
            slave_device_ids (list): 从设备ID列表
            
        Returns:
            bool: 是否成功
        """
        try:
            if not main_device_id or not slave_device_ids:
                console_log("主控设备或从设备为空，无法建立桥接", "WARN")
                return False
                
            console_log(f"建立群控桥接: 主控设备 {main_device_id} -> {len(slave_device_ids)} 个从设备")
            
            # 确保所有设备都可用
            all_devices = slave_device_ids + [main_device_id]
            available_devices = self.get_devices()
            available_ids = [device[0] for device in available_devices]
            
            missing_devices = [device_id for device_id in all_devices if device_id not in available_ids]
            if missing_devices:
                console_log(f"以下设备不可用: {', '.join(missing_devices)}", "WARN")
                return False
                
            # 保存群控相关设置
            self.sync_control_main_device = main_device_id
            self.sync_control_slave_devices = slave_device_ids.copy()
            
            # 可以在这里初始化一些群控预设或者特定设备的映射关系
            self.device_mapping = {}
            
            for slave_id in slave_device_ids:
                # 获取主设备和从设备信息
                main_size = self.get_screen_size(main_device_id)
                slave_size = self.get_screen_size(slave_id)
                
                if main_size and slave_size:
                    # 记录屏幕尺寸映射关系
                    self.device_mapping[slave_id] = {
                        "main_size": main_size,
                        "slave_size": slave_size,
                        "x_ratio": slave_size[0] / main_size[0],
                        "y_ratio": slave_size[1] / main_size[1]
                    }
                    
            console_log(f"群控桥接建立成功，已为 {len(self.device_mapping)} 个设备创建映射关系")
            return True
            
        except Exception as e:
            console_log(f"建立群控桥接时出错: {e}", "ERROR")
            return False 