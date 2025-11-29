#!/usr/bin/env python3
import os
import sys

def build_executables():
    # 从环境变量获取 SPECIAL_MATER_API
    special_api = os.environ.get('SPECIAL_MATER_API')
    
    if not special_api:
        print("错误: 未设置 SPECIAL_MATER_API 环境变量")
        sys.exit(1)
    
    # 读取原始代码
    with open('main.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 替换占位符
    content = content.replace('SPECIAL_MATER_API_PLACEHOLDER', special_api)
    
    # 写入临时文件
    with open('main_build.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    # 构建不同平台的可执行文件
    platforms = [
        ('windows', 'metar-service-windows.exe'),
        ('linux', 'metar-service-linux'),
        ('macos', 'metar-service-macos')
    ]
    
    for platform, output_name in platforms:
        print(f"构建 {platform} 版本: {output_name}")
        
        # 使用 PyInstaller 构建
        if platform == 'windows':
            os.system(f'pyinstaller --onefile --name "{output_name}" main_build.py')
        else:
            os.system(f'pyinstaller --onefile --name "{output_name}" main_build.py')
    
    # 清理临时文件
    if os.path.exists('main_build.py'):
        os.remove('main_build.py')
    
    print("构建完成！")

if __name__ == '__main__':
    build_executables()