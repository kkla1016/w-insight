# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch, MagicMock
import io
import json

from models.report_generator import ReportGenerator
from utils.config_manager import ConfigManager

class TestReportGeneratorPrice(unittest.TestCase):
    """
    測試 ReportGenerator 現股價格「網路優先，本機降級」的檢索邏輯。
    """

    def setUp(self):
        # 建立設定管理器（讀取 config.json，可用 MagicMock 隔離）
        self.config = MagicMock(spec=ConfigManager)
        self.config.get_folder_daily_price.return_value = "fake_price_dir"
        self.config.get_folder_institutional.return_value = "fake_inst_dir"
        self.config.get_folder_foreign_ownership.return_value = "fake_fore_dir"
        
        # 由於 ReportGenerator.__init__ 內部會自己載入 ConfigManager("config.json")，
        # 我們可以用 patch 或者是直接替換實例的 self._config
        with patch('models.report_generator.ReportGenerator._register_chinese_font', return_value=True):
            self.generator = ReportGenerator()
            self.generator._config = self.config

    @patch('urllib.request.urlopen')
    def test_fetch_web_price_success_regular(self, mock_urlopen):
        """
        測試網路獲取股價成功（回傳 regularMarketPrice）
        """
        # 模擬 API 回傳 json 數據
        fake_response_data = {
            "chart": {
                "result": [{
                    "meta": {
                        "symbol": "4916.TW",
                        "regularMarketPrice": 124.5,
                        "chartPreviousClose": 114.0
                    }
                }]
            }
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(fake_response_data).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # 執行測試
        price = self.generator._fetch_web_price("4916 事欣科")
        self.assertEqual(price, "124.50")

    @patch('urllib.request.urlopen')
    def test_fetch_web_price_fallback_to_previous(self, mock_urlopen):
        """
        測試當 regularMarketPrice 缺失時，fallback 至 chartPreviousClose
        """
        fake_response_data = {
            "chart": {
                "result": [{
                    "meta": {
                        "symbol": "4916.TW",
                        "chartPreviousClose": 114.0
                    }
                }]
            }
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(fake_response_data).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        price = self.generator._fetch_web_price("4916 事欣科")
        self.assertEqual(price, "114.00")

    @patch('urllib.request.urlopen')
    def test_fetch_web_price_network_failure(self, mock_urlopen):
        """
        測試網路失敗時傳回 None
        """
        mock_urlopen.side_effect = Exception("Connection Timeout")

        price = self.generator._fetch_web_price("4916 事欣科")
        self.assertIsNone(price)

    @patch('models.report_generator.ReportGenerator._fetch_web_price')
    @patch('models.report_generator.ReportGenerator._fetch_stock_data_from_excel')
    @patch('models.report_generator.ReportGenerator._find_latest_excel_in_dir')
    def test_get_chips_and_price_data_web_priority(self, mock_find_latest, mock_fetch_excel, mock_fetch_web_price):
        """
        測試 _get_chips_and_price_data 在股價網路成功時，優先採用網路股價，籌碼採用本機
        """
        # 1. 設定 mock 回傳值
        mock_find_latest.side_effect = lambda path: f"latest_file_in_{path}.xlsx"
        
        # 本機 Excel 中的價格為 114.00，法人為 +433，外資為 2.0
        # _fetch_stock_data_from_excel 被呼叫三次，分別對應價格、法人、外資
        mock_fetch_excel.side_effect = ["114.00", "-1365", "6.22"]
        
        # 網路最新的現股價格為 124.50
        mock_fetch_web_price.return_value = "124.50"

        # 2. 呼叫整合邏輯
        res = self.generator._get_chips_and_price_data("4916 事欣科")

        # 3. 驗證
        # 股價應為網路價格 124.50 元，法人為本機 -1365 張，外資為本機 6.22 %
        self.assertEqual(res["avg_price"], "124.50 元")
        self.assertEqual(res["net_buy"], "-1365 張")
        self.assertEqual(res["foreign_ratio"], "6.22 %")
        self.assertEqual(res["source"], "本機資料庫")

    @patch('models.report_generator.ReportGenerator._fetch_web_price')
    @patch('models.report_generator.ReportGenerator._fetch_stock_data_from_excel')
    @patch('models.report_generator.ReportGenerator._find_latest_excel_in_dir')
    def test_get_chips_and_price_data_local_fallback(self, mock_find_latest, mock_fetch_excel, mock_fetch_web_price):
        """
        測試當網路股價獲取失敗時，降級採用本機 Excel 中的股價
        """
        mock_find_latest.side_effect = lambda path: f"latest_file_in_{path}.xlsx"
        mock_fetch_excel.side_effect = ["114.00", "+433", "2.00"]
        
        # 網路股價獲取失敗
        mock_fetch_web_price.return_value = None

        res = self.generator._get_chips_and_price_data("4916 事欣科")

        # 股價降級採用本機 114.00 元
        self.assertEqual(res["avg_price"], "114.00 元")
        self.assertEqual(res["net_buy"], "+433 張")
        self.assertEqual(res["foreign_ratio"], "2.00 %")
        self.assertEqual(res["source"], "本機資料庫")

    @patch('os.path.exists')
    @patch('models.report_generator.ReportGenerator._find_latest_excel_in_dir')
    @patch('pandas.read_excel')
    def test_get_stock_code_by_name(self, mock_read_excel, mock_find_latest, mock_exists):
        """
        測試根據股票簡稱反查其代碼
        """
        # 1. 測試帶有代碼的輸入，應直接回傳代碼（不需讀取 Excel）
        code_direct = self.generator._get_stock_code_by_name("4916 \u4e8b\u6b23\u79d1")
        self.assertEqual(code_direct, "4916")
        
        # 2. 測試純名稱的輸入，應讀取本機 Excel 反查
        mock_exists.return_value = True
        mock_find_latest.return_value = "fake_price.xlsx"
        
        # 模擬 pandas 讀取 Excel 的 DataFrame 內容 (使用 Unicode 轉義以防編碼問題)
        import pandas as pd
        mock_df = pd.DataFrame({
            "\u8b49\u5238\u4ee3\u78bc": [8150, 4916],
            "\u8b49\u5238\u540d\u7a31": ["\u5357\u8302", "\u4e8b\u6b23\u79d1"]
        })
        mock_read_excel.return_value = mock_df
        
        code_lookup = self.generator._get_stock_code_by_name("\u4e8b\u6b23\u79d1")
        self.assertEqual(code_lookup, "4916")
        
        # 3. 測試找不到的名稱，應回傳 None
        code_not_found = self.generator._get_stock_code_by_name("\u4e0d\u5b58\u5728\u7684\u80a1\u7968")
        self.assertIsNone(code_not_found)

if __name__ == '__main__':
    unittest.main()
