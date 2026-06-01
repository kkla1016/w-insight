# -*- coding: utf-8 -*-
"""
W-Insight API 啟動伺服器
提供輕量級 HTTP API 接口，供 n8n 等自動化工具定時觸發啟動 W-Insight 桌面應用程式。
本服務僅使用 Python 內建標準函式庫，無需安裝額外依賴套件。
"""

import http.server
import socketserver
import subprocess
import os
import sys
import json

# 定義服務運行埠號
PORT = 8000

class StartWarrantHandler(http.server.SimpleHTTPRequestHandler):
    """
    自訂 HTTP 請求處理器，解析特定 API 路徑並觸發 W-Insight 啟動。
    """
    
    def _set_headers(self, status_code=200):
        """
        設定 JSON 回應標頭資訊
        """
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        # 允許跨網域請求 (CORS)，方便 Web 介面或 n8n 呼叫
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_OPTIONS(self):
        """
        處理 CORS 預檢請求
        """
        self._set_headers(200)

    def do_POST(self):
        """
        處理 POST 請求。接收到 /api/start 時觸發 W-Insight 應用程式啟動。
        """
        self._handle_start_request()

    def do_GET(self):
        """
        處理 GET 請求。支援 /api/start (方便瀏覽器點擊測試) 與 /api/status。
        """
        if self.path == '/api/status':
            self._handle_status_request()
        elif self.path == '/api/start':
            self._handle_start_request()
        else:
            # 處理未知路徑，回傳 404
            self._set_headers(404)
            response = {
                "status": "error",
                "message": "找不到請求的 API 端點。請使用 /api/start 啟動應用，或 /api/status 檢查狀態。"
            }
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))

    def _handle_start_request(self):
        """
        核心啟動邏輯：利用 subprocess.Popen 異步拉起 main.py GUI 桌面應用。
        """
        try:
            # 獲取當前指令碼所在目錄，確保 cwd 路徑正確
            script_dir = os.path.dirname(os.path.abspath(__file__))
            main_path = os.path.join(script_dir, 'main.py')
            
            if not os.path.exists(main_path):
                raise FileNotFoundError(f"找不到 W-Insight 主程式 main.py，路徑為: {main_path}")

            # 建立啟動標記，在 Windows 上開啟獨立新控制台，避免阻塞 API 伺服器
            creation_flags = 0
            if sys.platform == 'win32':
                creation_flags = subprocess.CREATE_NEW_CONSOLE

            # 異步啟動應用程式，不等待其結束即可回傳 HTTP 回應
            subprocess.Popen(
                [sys.executable, main_path],
                cwd=script_dir,
                creationflags=creation_flags
            )

            self._set_headers(200)
            response = {
                "status": "success",
                "message": "W-Insight 權證洞察系統啟動指令已成功送出！"
            }
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))
            print("[INFO] 已成功觸發 W-Insight 啟動指令")

        except Exception as e:
            self._set_headers(500)
            response = {
                "status": "error",
                "message": f"啟動應用程式時發生錯誤: {str(e)}"
            }
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))
            print(f"[ERROR] 啟動失敗: {str(e)}")

    def _handle_status_request(self):
        """
        回傳 API 伺服器本身的健康狀況與基本資訊。
        """
        self._set_headers(200)
        response = {
            "status": "online",
            "service": "W-Insight API Trigger Service",
            "version": "1.0.0",
            "platform": sys.platform
        }
        self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))


def run_server(port=PORT):
    """
    啟動 TCP 監聽服務，承載 HTTP API。
    """
    # 設置 Socket 位址重用，防止 Port 佔用
    socketserver.TCPServer.allow_reuse_address = True
    
    try:
        with socketserver.TCPServer(("", port), StartWarrantHandler) as httpd:
            print("=" * 60)
            print(f" W-Insight API 啟動服務已就緒！")
            print(f" 監聽埠號: http://localhost:{port}")
            print(f" - 啟動 API: http://localhost:{port}/api/start (支援 GET / POST)")
            print(f" - 狀態 API: http://localhost:{port}/api/status (支援 GET)")
            print("=" * 60)
            print("按下 Ctrl+C 可安全關閉服務...")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] 正在安全關閉 API 服務...")
    except Exception as e:
        print(f"[FATAL] 服務啟動異常: {str(e)}")


if __name__ == '__main__':
    run_server()
