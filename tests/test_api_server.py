# -*- coding: utf-8 -*-
"""
W-Insight API 啟動服務單元測試
"""

import unittest
from unittest.mock import patch, MagicMock
import threading
import urllib.request
import urllib.error
import json
import time
import socketserver

# 載入被測試模組
from api_server import StartWarrantHandler

class TestApiServer(unittest.TestCase):
    """
    測試 W-Insight API 啟動服務端點的功能，確保在不同請求方法與路徑下的行為正確。
    """
    
    @classmethod
    def setUpClass(cls):
        """
        在測試類別初始化時，於獨立執行緒中啟動測試用的 HTTP 伺服器
        """
        # 使用 8085 Port 進行測試，避免與可能運行中的 8000 Port 衝突
        cls.test_port = 8085
        socketserver.TCPServer.allow_reuse_address = True
        cls.httpd = socketserver.TCPServer(("", cls.test_port), StartWarrantHandler)
        
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever)
        cls.server_thread.daemon = True
        cls.server_thread.start()
        # 給伺服器時間初始化
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        """
        測試結束後，關閉測試用的伺服器
        """
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def test_status_endpoint(self):
        """
        測試 /api/status 狀態端點，確認其回傳 status 為 online 的 JSON。
        """
        url = f"http://localhost:{self.test_port}/api/status"
        try:
            response = urllib.request.urlopen(url)
            data = response.read().decode('utf-8')
            json_data = json.loads(data)
            
            self.assertEqual(response.status, 200)
            self.assertEqual(json_data["status"], "online")
            self.assertEqual(json_data["service"], "W-Insight API Trigger Service")
        except urllib.error.URLError as e:
            self.fail(f"請求 /api/status 失敗: {e}")

    @patch('subprocess.Popen')
    @patch('os.path.exists')
    def test_start_endpoint_success(self, mock_exists, mock_popen):
        """
        測試 /api/start 啟動端點 (成功路徑)。
        使用 Mock 攔截真實進程建立，確保測試環境下不彈出真實 GUI。
        """
        # 模擬 main.py 檔案確實存在
        mock_exists.return_value = True
        mock_popen.return_value = MagicMock()
        
        url = f"http://localhost:{self.test_port}/api/start"
        try:
            # 發送 POST 請求
            req = urllib.request.Request(url, method='POST')
            response = urllib.request.urlopen(req)
            data = response.read().decode('utf-8')
            json_data = json.loads(data)
            
            self.assertEqual(response.status, 200)
            self.assertEqual(json_data["status"], "success")
            self.assertIn("啟動指令已成功送出", json_data["message"])
            
            # 確保 subprocess.Popen 確實被呼叫
            mock_popen.assert_called_once()
        except urllib.error.URLError as e:
            self.fail(f"請求 /api/start 失敗: {e}")

    def test_invalid_endpoint(self):
        """
        測試未知端點應回傳 404 狀態碼與錯誤 JSON。
        """
        url = f"http://localhost:{self.test_port}/api/invalid_path"
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(url)
        
        self.assertEqual(cm.exception.code, 404)
        
        # 驗證回傳的 JSON 錯誤訊息
        error_content = cm.exception.read().decode('utf-8')
        json_error = json.loads(error_content)
        self.assertEqual(json_error["status"], "error")
        self.assertIn("找不到請求的 API 端點", json_error["message"])
