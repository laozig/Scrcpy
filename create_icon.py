#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 此文件用于生成ScrcpyGUI的应用图标
# 2025-05-10: 更新为测试用绿色图标

from PIL import Image, ImageDraw, ImageFont
import os
import sys
import io
import base64
import struct
import subprocess
import platform

def get_icon_bytes():
    """
    创建图标并返回图标的字节数据
    这样可以在应用程序内部直接使用图标数据，不需要依赖外部文件
    """
    # 创建尺寸 - 对Windows 特别重要的是16x16, 32x32和48x48
    sizes = [16, 32, 48, 64, 128, 256]
    images = []
    
    # 为每个尺寸创建图标
    for size in sizes:
        # 创建画布，使用RGBA模式支持透明度
        image = Image.new('RGBA', (size, size), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # 绘制圆形背景 - 使用鲜艳的绿色作为测试颜色
        margin = int(size * 0.1)
        draw.ellipse([(margin, margin), (size - margin, size - margin)], 
                     fill=(46, 204, 113, 255))  # 鲜艳的绿色背景
        
        # 绘制一个简单的"S"形状
        width = int(size * 0.5)
        height = int(size * 0.6)
        x_center = size // 2
        y_center = size // 2
        stroke_width = max(1, int(size * 0.15))
        
        # S 形状的点
        points = [
            (x_center - width//2, y_center - height//3),
            (x_center + width//2, y_center - height//2),
            (x_center - width//2, y_center + height//3),
            (x_center + width//2, y_center + height//2)
        ]
        draw.line(points, fill=(255, 255, 255, 255), width=stroke_width)
        
        # 添加到图像列表
        images.append(image)
    
    # 将图标保存到字节流中
    icon_bytes = io.BytesIO()
    images[0].save(icon_bytes, format='ICO', sizes=[(s, s) for s in sizes], 
                   append_images=images[1:])
    icon_bytes.seek(0)
    return icon_bytes.read()

def create_simple_icon(output_path="1.ico"):
    """
    创建一个简单的图标文件作为应用程序的默认图标
    使用PIL库绘制一个带有'S'字母的简单图标
    """
    try:
        # 创建尺寸 - 对Windows 特别重要的是16x16, 32x32和48x48
        sizes = [16, 32, 48, 64, 128, 256]
        images = []
        
        # 为每个尺寸创建图标
        for size in sizes:
            # 创建画布，使用RGBA模式支持透明度
            image = Image.new('RGBA', (size, size), color=(0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            
            # 绘制圆形背景 - 使用主题蓝色
            margin = int(size * 0.1)
            draw.ellipse([(margin, margin), (size - margin, size - margin)], 
                         fill=(66, 135, 245, 255))  # 主题蓝色背景
            
            # 绘制一个简单的"S"形状
            width = int(size * 0.5)
            height = int(size * 0.6)
            x_center = size // 2
            y_center = size // 2
            stroke_width = max(1, int(size * 0.15))
            
            # S 形状的点
            points = [
                (x_center - width//2, y_center - height//3),
                (x_center + width//2, y_center - height//2),
                (x_center - width//2, y_center + height//3),
                (x_center + width//2, y_center + height//2)
            ]
            draw.line(points, fill=(255, 255, 255, 255), width=stroke_width)
            
            # 添加到图像列表
            images.append(image)
        
        # 尝试不同的保存方法
        try:
            # 方法1: 使用所有尺寸保存 - 经典方法
            images[0].save(output_path, format='ICO', sizes=[(s, s) for s in sizes], 
                           append_images=images[1:])
            
            # 验证ICO文件
            if not os.path.exists(output_path) or os.path.getsize(output_path) < 100:
                raise Exception("ICO文件太小或不存在，尝试备用方法")
                
        except Exception as e:
            print(f"第一种保存方法失败: {e}")
            
            try:
                # 方法2: 仅保存一个尺寸 (32x32) - Windows最常用
                images[1].save(output_path, format='ICO')  # 32x32
                
                if not os.path.exists(output_path) or os.path.getsize(output_path) < 100:
                    raise Exception("第二种方法也生成了无效的ICO文件")
            except Exception as e2:
                print(f"第二种保存方法也失败: {e2}")
                
                try:
                    # 方法3: 使用单一最大尺寸
                    largest = images[-1]  # 256x256
                    largest.save(output_path, format='ICO')
                except Exception as e3:
                    print(f"所有方法都失败: {e3}")
                    return None
        
        print(f"图标文件已创建: {os.path.abspath(output_path)}")
        print(f"图标文件大小: {os.path.getsize(output_path)} 字节")
        return os.path.abspath(output_path)
        
    except Exception as e:
        print(f"创建图标时发生错误: {e}")
        return None

def get_icon_base64():
    """
    获取图标的Base64编码字符串，方便在代码中直接使用
    """
    icon_bytes = get_icon_bytes()
    return base64.b64encode(icon_bytes).decode('utf-8')

def create_resource_script(icon_path="1.ico", output_path="icon_resource.rc"):
    """
    创建Windows资源脚本文件，用于设置文件的图标属性
    """
    # 资源脚本内容
    rc_content = f"""
// ScrcpyGUI 图标资源
#define IDI_ICON1 101
IDI_ICON1 ICON DISCARDABLE "{icon_path}"
"""
    
    # 写入资源脚本文件
    with open(output_path, 'w') as rc_file:
        rc_file.write(rc_content)
    
    print(f"已创建资源脚本文件: {os.path.abspath(output_path)}")
    return os.path.abspath(output_path)

def set_file_icon(exe_path, icon_path="1.ico"):
    """
    为可执行文件设置图标属性，使其在文件浏览器中显示
    注意：此函数仅在Windows环境下有效，且需要相应的开发工具
    """
    try:
        # 创建资源脚本
        rc_path = create_resource_script(icon_path)
        
        # 编译资源脚本 (需要安装Windows SDK)
        resource_path = rc_path.replace('.rc', '.res')
        
        # 调用rc.exe编译资源脚本
        subprocess.run(['rc.exe', '/nologo', rc_path], check=True)
        
        # 将资源文件附加到exe
        # 这一步通常需要专业的工具，如ResourceHacker等
        print(f"资源文件已创建: {resource_path}")
        print(f"请使用ResourceHacker等工具将资源文件手动附加到EXE: {exe_path}")
        
        return True
    except Exception as e:
        print(f"设置文件图标属性失败: {e}")
        return False

def create_icon_images(output_path, size=256):
    try:
        # 创建一个新的透明图像
        image = Image.new('RGBA', (size, size), color=(255, 255, 255, 0))
        draw = ImageDraw.Draw(image)

        # 绘制圆形背景 - 使用主题蓝色
        circle_color = (66, 135, 245)  # 主题蓝色
        draw.ellipse((0, 0, size-1, size-1), fill=circle_color)
        
        # 绘制字母S作为中心标志 - 白色
        try:
            # 尝试加载字体
            font_size = int(size * 0.6)  # 字体大小为图像大小的60%
            try:
                # 尝试加载系统字体
                font = ImageFont.truetype("arial.ttf", font_size)
            except:
                try:
                    # 在不同系统上尝试不同的字体
                    if platform.system() == "Windows":
                        font = ImageFont.truetype("arial.ttf", font_size)
                    elif platform.system() == "Darwin":  # macOS
                        font = ImageFont.truetype("AppleGothic.ttf", font_size)
                    else:  # Linux
                        font = ImageFont.truetype("DejaVuSans.ttf", font_size)
                except:
                    # 如果字体加载失败，使用默认字体
                    font = ImageFont.load_default()
            
            # 计算文字位置，使其居中
            text = "S"
            text_width, text_height = draw.textsize(text, font=font)
            position = ((size - text_width) / 2, (size - text_height) / 2 - font_size * 0.1)
            
            # 绘制文字
            draw.text(position, text, fill=(255, 255, 255, 255), font=font)
        except Exception as e:
            # 如果绘制文字失败，绘制一个简单的白色圆圈作为替代
            center = size / 2
            radius = size / 4
            draw.ellipse((center - radius, center - radius, 
                          center + radius, center + radius), 
                         fill=(255, 255, 255, 255))
        
        # 保存图像
        # 不要保存调试图像
        
        # 保存最终图标
        return image
    except Exception as e:
        print(f"创建图标时发生错误: {e}")
        return None

if __name__ == "__main__":
    # 创建图标文件
    icon_path = create_simple_icon()
    if icon_path:
        print(f"请将此图标文件用于您的应用程序: {icon_path}")
        # 确认图标文件存在
        if os.path.exists(icon_path):
            print(f"确认图标文件存在，大小: {os.path.getsize(icon_path)} 字节")
        else:
            print("错误: 图标文件不存在!")
    else:
        print("创建图标文件失败!") 