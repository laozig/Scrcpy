#!/usr/bin/env python
# -*- coding: utf-8 -*-

# 此文件用于生成ScrcpyGUI的应用图标
# 2025-05-10: 更新为测试用绿色图标

from PIL import Image, ImageDraw
import os
import sys

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
            
            # 保存PNG用于验证
            debug_dir = "icon_debug"
            if not os.path.exists(debug_dir):
                os.makedirs(debug_dir)
            image.save(os.path.join(debug_dir, f"icon_{size}x{size}.png"))
        
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
        
        # 创建一个备用BMP格式的图标（某些Windows应用更喜欢这种格式）
        try:
            bmp_path = output_path.replace('.ico', '.bmp')
            images[3].convert('RGB').save(bmp_path)  # 64x64 BMP
            print(f"已创建备用BMP图标: {bmp_path}")
        except:
            pass
        
        print(f"图标文件已创建: {os.path.abspath(output_path)}")
        print(f"图标文件大小: {os.path.getsize(output_path)} 字节")
        return os.path.abspath(output_path)
        
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