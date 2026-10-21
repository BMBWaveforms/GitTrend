#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地静态服务器：让 dashboard.html 能自动拉取最新数据。

看板自带自动刷新，但它靠 fetch() 读 data/latest.json，而 file:// 下浏览器
会禁止这种请求。所以「动态更新」的正确打开方式是：

    1) 跑采集（每天一次即可，或者带 --loop 让它自己定时跑）
         python3 radar.py --loop 360
    2) 再开一个终端，跑这个服务器
         python3 serve.py
    3) 浏览器会自动打开 http://localhost:8765/dashboard.html

之后只要 data/latest.json 有更新，已经开着的页面每 60 秒会自动拉取并刷新，
不用手动刷新浏览器，也不用关掉重开。

用法:
    python3 serve.py               # 默认端口 8765，自动打开浏览器
    python3 serve.py 9000          # 指定端口
    python3 serve.py --no-browser  # 不自动打开浏览器（launchd 常驻用）
"""

import http.server
import socketserver
import sys
import threading
import webbrowser
from functools import partial
from pathlib import Path

PORT = 8765
NO_BROWSER = False
for a in sys.argv[1:]:
    if a == "--no-browser":
        NO_BROWSER = True
    elif a.isdigit():
        PORT = int(a)

ROOT = str(Path(__file__).resolve().parent)


class CORSHandler(http.server.SimpleHTTPRequestHandler):
    """带 CORS 头的静态服务：允许 file:// 打开的看板跨域拉取 latest.json。"""

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


Handler = partial(CORSHandler, directory=ROOT)
socketserver.TCPServer.allow_reuse_address = True


def open_browser():
    webbrowser.open(f"http://localhost:{PORT}/dashboard.html")


if __name__ == "__main__":
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"服务已启动: http://localhost:{PORT}/dashboard.html")
        if NO_BROWSER:
            print("(--no-browser 模式，不自动打开浏览器)")
        else:
            threading.Timer(0.6, open_browser).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止")
