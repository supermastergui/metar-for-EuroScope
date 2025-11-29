#!/usr/bin/env python3
import os
import sys

def build_executable():
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
    
    # 获取输出文件名（从命令行参数或环境变量）
    output_name = os.environ.get('OUTPUT_NAME', 'metar-service')
    
    print(f"构建版本: {output_name}")
    
    # 使用 PyInstaller 构建
    os.system(f'pyinstaller --onefile --name "{output_name}" main_build.py')
    
    # 清理临时文件
    if os.path.exists('main_build.py'):
        os.remove('main_build.py')
    
    print("构建完成！")

if __name__ == '__main__':
    build_executable()