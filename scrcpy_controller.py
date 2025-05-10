#!/usr/bin/env python
# -*- coding: utf-8 -*-

import subprocess
import shlex
import os
import re
import platform
import threading
import time

"""
Scrcpy控制器模块，用于与Android设备进行通信和控制。

修复了以下问题：
1. 修复了execute_adb_command方法中的设备ID处理：确保正确传递设备ID参数
2. 改进了命令执行逻辑：将check参数设为False，以便捕获错误但继续执行
3. 添加了更详细的错误处理：添加了返回码检查和错误输出处理
4. 改进了日志输出：添加了更多的调试信息，方便排查问题
"""

class ScrcpyController:
    def __init__(self):
        self.process = None
        self.system = platform.system()
        
    def get_devices(self):
        """
        调用 adb devices 命令获取已连接的安卓设备列表
        
        Returns:
            list: 设备列表，每个元素为(device_id, model)的元组
        """
        try:
            kwargs = {}
            if self.system == 'Windows':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                
            result = subprocess.run(
                ["adb", "devices"], 
                capture_output=True, 
                text=True, 
                check=False,
                **kwargs
            )
            
            if result.returncode != 0:
                print(f"获取设备列表失败: {result.stderr}")
                return []
            
            devices = []
            lines = result.stdout.strip().split('\n')
            
            # 跳过第一行（标题行）
            for line in lines[1:]:
                if not line.strip():
                    continue
                    
                # 支持不同格式的设备标识
                parts = line.split('\t')
                if len(parts) >= 2:
                    device_id = parts[0].strip()
                    status = parts[1].strip()
                    
                    # 只处理已认证的连接设备
                    if status == 'device':
                        # 获取设备型号信息
                        try:
                            kwargs = {}
                            if self.system == 'Windows':
                                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                                
                            model_result = subprocess.run(
                                ["adb", "-s", device_id, "shell", "getprop", "ro.product.model"],
                                capture_output=True,
                                text=True,
                                check=False,
                                timeout=2, # 设置超时时间
                                **kwargs
                            )
                            if model_result.returncode == 0:
                                model = model_result.stdout.strip()
                                if not model:
                                    model = "未知设备"
                                devices.append((device_id, model))
                            else:
                                devices.append((device_id, "未知设备"))
                        except Exception as e:
                            devices.append((device_id, "未知设备"))
            
            return devices
        except Exception as e:
            print(f"获取设备列表出错: {e}")
            return []
            
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
        cmd = ["scrcpy"]
        
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
        # 如果有正在运行的进程，先停止
        if self.process and self.process.poll() is None:
            self.stop_scrcpy()
            
        try:
            # Windows下需要设置creationflags以正确显示命令行窗口
            kwargs = {}
            if self.system == 'Windows':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            
            self.process = subprocess.Popen(
                command,
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
                
            return True, " ".join(command)
        except Exception as e:
            return False, str(e)
            
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
                print(f"停止进程错误: {e}")
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
                ["adb", "version"], 
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
        except:
            results["adb"] = False
            results["adb_version"] = None
            
        # 检查scrcpy
        try:
            kwargs = {}
            if self.system == 'Windows':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                
            scrcpy_version = subprocess.run(
                ["scrcpy", "--version"], 
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
        except:
            results["scrcpy"] = False
            results["scrcpy_version"] = None
            
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
            cmd = ["adb"]
            if device_id:
                cmd.extend(["-s", device_id])
            cmd.extend(["tcpip", str(port)])
            
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
                ["adb", "connect", connection_string],
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
            cmd = ["adb", "disconnect"]
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
            cmd = ["adb"]
            if device_id:
                cmd.extend(["-s", device_id])
            cmd.extend(["exec-out", "screencap", "-p"])
            
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
            model_cmd = ["adb", "-s", device_id, "shell", "getprop", "ro.product.model"]
            model_result = subprocess.run(model_cmd, capture_output=True, text=True, check=True, **kwargs)
            info["model"] = model_result.stdout.strip()
            
            # 获取安卓版本
            version_cmd = ["adb", "-s", device_id, "shell", "getprop", "ro.build.version.release"]
            version_result = subprocess.run(version_cmd, capture_output=True, text=True, check=True, **kwargs)
            info["android_version"] = version_result.stdout.strip()
            
            # 获取屏幕分辨率
            res_cmd = ["adb", "-s", device_id, "shell", "wm", "size"]
            res_result = subprocess.run(res_cmd, capture_output=True, text=True, check=True, **kwargs)
            res_output = res_result.stdout.strip()
            res_match = re.search(r'Physical size: (\d+x\d+)', res_output)
            if res_match:
                info["resolution"] = res_match.group(1)
                
            return info
        except Exception as e:
            print(f"获取设备信息出错: {e}")
            return info

    def execute_adb_command(self, command, device_id=None):
        """
        执行ADB命令并返回结果
        
        Args:
            command (str): ADB命令字符串，不包含"adb"前缀
            device_id (str, optional): 设备ID，如果不为None，会自动添加-s参数
            
        Returns:
            tuple: (成功标志, 输出结果)
        """
        try:
            # 分割命令字符串
            cmd_parts = shlex.split(command)
            
            # 完整的ADB命令
            full_cmd = ["adb"]
            
            # 如果提供了设备ID，添加-s参数
            if device_id:
                full_cmd.extend(["-s", device_id])
                
            full_cmd.extend(cmd_parts)
            
            print(f"执行ADB命令: {' '.join(full_cmd)}")  # 调试输出
            
            # 执行命令
            try:
                kwargs = {}
                if self.system == 'Windows':
                    kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                    
                result = subprocess.run(
                    full_cmd,
                    capture_output=True,
                    text=True,
                    check=False,  # 修改为False，以便捕获错误但继续执行
                    timeout=15,  # 添加超时时间，防止命令卡住
                    **kwargs
                )
                
                # 检查命令是否成功执行
                if result.returncode != 0:
                    error_output = result.stderr if result.stderr else result.stdout
                    print(f"命令执行失败(返回码 {result.returncode}): {error_output}")
                    return False, error_output
                
                # 合并标准输出和错误输出
                output = result.stdout
                if result.stderr:
                    output += "\n" + result.stderr
                    
                # 检查输出是否包含错误信息
                if "error" in output.lower() or "failed" in output.lower() or "not found" in output.lower():
                    print(f"命令执行出现错误提示: {output}")
                    return False, output
                    
                return True, output
            except subprocess.TimeoutExpired:
                print(f"命令执行超时: {' '.join(full_cmd)}")
                return False, "命令执行超时，请检查设备连接状态"
                
        except subprocess.CalledProcessError as e:
            # 命令执行错误
            error_output = e.stdout if e.stdout else ""
            if e.stderr:
                error_output += "\n" + e.stderr
            print(f"命令执行错误: {error_output}")
            return False, error_output
        except Exception as e:
            # 其他异常
            print(f"执行命令时发生异常: {str(e)}")
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
                
            cmd = ["adb", "-s", device_id, "shell", "getprop", "ro.product.brand"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False, **kwargs)
            if result.returncode == 0:
                return result.stdout.strip()
            return "未知品牌"
        except Exception:
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
            brand_cmd = ["adb", "-s", device_id, "shell", "getprop", "ro.product.brand"]
            brand_result = subprocess.run(brand_cmd, capture_output=True, text=True, check=False, **kwargs)
            if brand_result.returncode == 0:
                info["brand"] = brand_result.stdout.strip()
                
            # 获取型号
            model_cmd = ["adb", "-s", device_id, "shell", "getprop", "ro.product.model"]
            model_result = subprocess.run(model_cmd, capture_output=True, text=True, check=False, **kwargs)
            if model_result.returncode == 0:
                info["model"] = model_result.stdout.strip()
                
            # 获取Android版本
            android_cmd = ["adb", "-s", device_id, "shell", "getprop", "ro.build.version.release"]
            android_result = subprocess.run(android_cmd, capture_output=True, text=True, check=False, **kwargs)
            if android_result.returncode == 0:
                info["android"] = android_result.stdout.strip()
                
            return info
        except Exception as e:
            print(f"获取设备信息出错: {e}")
            return info 