#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import subprocess
import json
import platform
from datetime import datetime

def get_platform_info():
    """获取平台信息"""
    return {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor()
    }

def execute_command(command, shell=False):
    """执行系统命令并返回结果"""
    try:
        result = subprocess.run(
            command, 
            shell=shell, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "code": result.returncode
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "code": -1
        }

def save_settings(settings, filename):
    """保存设置到JSON文件"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
        return True
    except Exception:
        return False

def load_settings(filename, default=None):
    """从JSON文件加载设置"""
    if default is None:
        default = {}
        
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        return default
    except Exception:
        return default

def format_timestamp(timestamp=None, format="%Y-%m-%d %H:%M:%S"):
    """格式化时间戳"""
    if timestamp is None:
        timestamp = datetime.now()
    elif isinstance(timestamp, (int, float)):
        timestamp = datetime.fromtimestamp(timestamp)
    return timestamp.strftime(format)

def parse_adb_device_output(output):
    """解析ADB设备列表输出"""
    devices = []
    lines = output.strip().split('\n')
    
    if len(lines) <= 1:  # 只有标题行
        return devices
    
    for line in lines[1:]:  # 跳过标题行
        parts = line.strip().split('\t')
        if len(parts) >= 2:
            device_id = parts[0].strip()
            status = parts[1].strip()
            devices.append({
                "id": device_id,
                "status": status
            })
    
    return devices

def extract_ip_from_ifconfig(output):
    """从ifconfig/ip addr输出中提取IP地址"""
    ip_pattern = r'inet\s+(?:addr:)?(\d+\.\d+\.\d+\.\d+)'
    match = re.search(ip_pattern, output)
    if match:
        return match.group(1)
    return None

def human_readable_size(size, decimal_places=2):
    """将字节大小转换为人类可读的格式"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
        if size < 1024.0 or unit == 'PB':
            break
        size /= 1024.0
    return f"{size:.{decimal_places}f} {unit}"

def is_process_running(process_name):
    """检查进程是否正在运行"""
    system = platform.system()
    
    if system == "Windows":
        command = f'tasklist /FI "IMAGENAME eq {process_name}" /NH'
        result = execute_command(command, shell=True)
        return process_name.lower() in result["stdout"].lower()
    elif system == "Darwin":  # macOS
        command = ["pgrep", process_name]
        result = execute_command(command)
        return result["success"]
    else:  # Linux
        command = ["pgrep", process_name]
        result = execute_command(command)
        return result["success"] 