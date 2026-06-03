"""
PDF 報告檔名生成規則單元測試
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from controllers.app_controller import AppController
from utils.config_manager import ConfigManager


class TestPdfExportFilename:
    """測試匯出 PDF 檔名規格之測試類別"""

    @pytest.fixture
    def controller(self, tmp_path):
        # 1. 建立測試用的 Config 檔案與 ConfigManager
        batch_dir = tmp_path / "mock_batch"
        batch_dir.mkdir(exist_ok=True)
        out_dir = tmp_path / "mock_out"
        out_dir.mkdir(exist_ok=True)
        
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(f'{{"output_dir": "{out_dir.as_posix()}", "batch_stock_folder": "{batch_dir.as_posix()}"}}')
        config = ConfigManager(str(cfg_file))
        
        # 2. 初始化 AppController，使用 Mock 隔離相依模組
        with patch('controllers.app_controller.DataLoader'), \
             patch('controllers.app_controller.WarrantFilter'), \
             patch('controllers.app_controller.ReportGenerator'), \
             patch('controllers.app_controller.TradingStrategy'):
            ctrl = AppController(config=config)
            ctrl._config = config
            
            # 填充非空 DataFrame 防止 pre-check 阻擋
            ctrl._phase1 = pd.DataFrame({"dummy": [1]})
            ctrl._phase2 = pd.DataFrame({"dummy": [1]})
            ctrl._v2_class_a = pd.DataFrame({"dummy": [1]})
            ctrl._v2_class_b = pd.DataFrame({"dummy": [1]})
            
            # Mock 掉 report 實體
            ctrl._report = MagicMock()
            return ctrl

    def test_single_pdf_export_filename_format(self, controller):
        """測試單一匯出 PDF 報告時，產生的檔名前綴與時間戳記格式是否正確"""
        # 執行匯出
        controller.export_pdf(stock_name="3189景碩", output_dir="/mock_out")
        
        # 驗證是否呼叫 PDF 產生函式
        assert controller._report.generate_report.call_count == 1
        assert controller._report.generate_v2_report.call_count == 1
        
        # 取得輸出路徑參數
        args_v1 = controller._report.generate_report.call_args[1]
        args_v2 = controller._report.generate_v2_report.call_args[1]
        
        path_v1 = args_v1['output_path']
        path_v2 = args_v2['output_path']
        
        import re
        # 預期格式: 3189景碩_wr_YYYYMMDD_HHMMSS.pdf
        pattern_v1 = r"3189景碩_wr_\d{8}_\d{6}\.pdf$"
        pattern_v2 = r"3189景碩_wr_v2_\d{8}_\d{6}\.pdf$"
        
        assert re.search(pattern_v1, path_v1) is not None, f"V1 檔名格式錯誤: {path_v1}"
        assert re.search(pattern_v2, path_v2) is not None, f"V2 檔名格式錯誤: {path_v2}"

    def test_batch_pdf_export_filename_format(self, controller):
        """測試一鍵批次匯出 PDF 時，個股檔名格式與統一時間戳記是否正確"""
        controller._raw_df = pd.DataFrame({"dummy": [1]})
        
        # Mock 批次檔案搜尋與解析
        controller._find_latest_excel = MagicMock(return_value="/mock_batch/list.xlsx")
        controller._parse_batch_stock_list = MagicMock(return_value=["3189景碩", "2330台積電"])
        
        # Mock 篩選過濾器之回傳值
        dummy_df = pd.DataFrame({"dummy": [1]})
        controller._filter.search_by_stock = MagicMock(return_value=dummy_df)
        controller._filter.filter_stock_phase1 = MagicMock(return_value=dummy_df)
        controller._filter.filter_stock_phase2 = MagicMock(return_value=dummy_df)
        controller._filter.detect_stock_iv_warnings = MagicMock(return_value=pd.DataFrame())
        controller._filter.filter_v2_class_a = MagicMock(return_value=dummy_df)
        controller._filter.filter_v2_class_b = MagicMock(return_value=dummy_df)
        
        # 執行批次匯出
        controller.export_batch_pdf()
        
        # 驗證總共呼叫次數 (共 2 檔股票，雙版本)
        assert controller._report.generate_report.call_count == 2
        assert controller._report.generate_v2_report.call_count == 2
        
        # 取得產出路徑
        calls_v1 = controller._report.generate_report.call_args_list
        calls_v2 = controller._report.generate_v2_report.call_args_list
        
        path_v1_1 = calls_v1[0][1]['output_path']
        path_v1_2 = calls_v1[1][1]['output_path']
        path_v2_1 = calls_v2[0][1]['output_path']
        path_v2_2 = calls_v2[1][1]['output_path']
        
        import re
        pattern_v1_1 = r"3189景碩_wr_(\d{8}_\d{6})\.pdf$"
        pattern_v1_2 = r"2330台積電_wr_(\d{8}_\d{6})\.pdf$"
        pattern_v2_1 = r"3189景碩_wr_v2_(\d{8}_\d{6})\.pdf$"
        pattern_v2_2 = r"2330台積電_wr_v2_(\d{8}_\d{6})\.pdf$"
        
        m_v1_1 = re.search(pattern_v1_1, path_v1_1)
        m_v1_2 = re.search(pattern_v1_2, path_v1_2)
        m_v2_1 = re.search(pattern_v2_1, path_v2_1)
        m_v2_2 = re.search(pattern_v2_2, path_v2_2)
        
        assert m_v1_1 is not None, f"批次1 V1 格式錯誤: {path_v1_1}"
        assert m_v1_2 is not None, f"批次2 V1 格式錯誤: {path_v1_2}"
        assert m_v2_1 is not None, f"批次1 V2 格式錯誤: {path_v2_1}"
        assert m_v2_2 is not None, f"批次2 V2 格式錯誤: {path_v2_2}"
        
        # 驗證不同個股的檔名時間戳記完全一致 (統一時間戳)
        ts1_v1 = m_v1_1.group(1)
        ts2_v1 = m_v1_2.group(1)
        ts1_v2 = m_v2_1.group(1)
        ts2_v2 = m_v2_2.group(1)
        
        assert ts1_v1 == ts2_v1 == ts1_v2 == ts2_v2, f"批次時間戳記不一致: {ts1_v1}, {ts2_v1}, {ts1_v2}, {ts2_v2}"
