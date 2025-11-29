# metar-for-EuroScope

本项目用于将 METAR 报文（气象自动服务）以 API 形式提供给 EuroScope（模拟飞行管制软件）进行调用，支持多重数据源自动切换。

## 项目介绍

- **核心功能**：支持 EuroScope 及其他 VATSIM 仿真相关平台，按机场代码查询最新 METAR 并返回文本数据。
- **接口特点**：
  - 提供 `/机场代码` 路径快速查询（如 `http://your-server:8000/ZSSS`）。
  - 多个数据源自动切换，优先主官方源，其次备用、第三方源，确保最大可用性。
  - 已适配 Python 打包为 EXE，可直接部署于 Windows/Linux/Mac。

## EuroScope对接说明

**EuroScope使用场景：**
1. 启动本服务（如打包后 EXE），后台运行。
2. 在 EuroScope 的 METAR 插件或自动资料配置中填写本服务地址，如 `http://localhost:8000/{ICAO}`。
3. 填写机场代码（示例：ZSSS、ZSPD），EuroScope 即可自动获取最新 METAR。

**快速测试：**
```shell
# 运行服务
python main.py
# 在浏览器中验证
http://localhost:8000/ZSSS
# 打包为可执行文件（建议用 PyInstaller，见 workflow 配置）
```

## 部署方式

- 可在本地服务器、云服务器上运行。
- 支持 Windows、Linux、macOS。
- 推荐直接下载 Release 中的 EXE 或按 `requirements.txt` 安装依赖后运行源码。

## 运行环境

- Python 3.10 及以上
- 依赖详见 `requirements.txt`

## 使用方法

1. 下载 release 或安装依赖：
   ```shell
   pip install -r requirements.txt
   python main.py
   ```
2. 访问 `http://localhost:8000/{ICAO}` 获取 METAR。

## MIT License

本项目使用 MIT 协议，欢迎自由使用、修改和分发！

```
MIT License

Copyright (c) 2025 supermastergui

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## 联系与反馈

如有建议与问题，欢迎在 Issues 中反馈。