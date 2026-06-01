"""
ConfigManager 單元測試
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import json
import tempfile
from pathlib import Path
from utils.config_manager import ConfigManager


@pytest.fixture
def tmp_config(tmp_path):
    """建立暫存目錄中的 ConfigManager"""
    config_file = tmp_path / "config.json"
    return ConfigManager(str(config_file))


class TestConfigManager:
    """ConfigManager 測試集"""

    def test_load_defaults_when_no_file(self, tmp_config):
        """不存在設定檔時應使用預設值"""
        assert tmp_config.get_excel_path() == "20260527172302DataExport.xlsx"
        assert tmp_config.get_iv_warning_threshold() == 1.5

    def test_auto_create_config_file(self, tmp_path):
        """初始化時應自動建立 config.json"""
        config_file = tmp_path / "config.json"
        ConfigManager(str(config_file))
        assert config_file.exists()

    def test_set_excel_path(self, tmp_config):
        """設定 Excel 路徑後應可讀回"""
        tmp_config.set_excel_path("new_data.xlsx")
        assert tmp_config.get_excel_path() == "new_data.xlsx"

    def test_set_output_dir(self, tmp_config):
        """設定輸出目錄後應可讀回"""
        tmp_config.set_output_dir("/some/path")
        assert tmp_config.get_output_dir() == "/some/path"

    def test_phase1_params_structure(self, tmp_config):
        """階段一參數應包含所有必要鍵"""
        params = tmp_config.get_phase1_params()
        for key in ["delta_min", "delta_max", "remaining_days_min",
                    "iv_hv_min", "iv_hv_max", "min_volume", "min_underlying_roi"]:
            assert key in params

    def test_phase2_params_structure(self, tmp_config):
        """階段二參數應包含所有必要鍵"""
        params = tmp_config.get_phase2_params()
        for key in ["delta_min", "delta_max", "remaining_days_min",
                    "remaining_days_max", "min_leverage", "iv_hv_max",
                    "min_volume", "min_underlying_roi"]:
            assert key in params

    def test_persistence_after_save(self, tmp_path):
        """儲存設定後重新載入應維持一致"""
        config_file = str(tmp_path / "config.json")
        cm1 = ConfigManager(config_file)
        cm1.set_excel_path("test_data.xlsx")

        cm2 = ConfigManager(config_file)
        assert cm2.get_excel_path() == "test_data.xlsx"

    def test_corrupted_config_uses_defaults(self, tmp_path):
        """損壞的設定檔應 fallback 到預設值"""
        config_file = tmp_path / "config.json"
        config_file.write_text("{ invalid json }", encoding="utf-8")
        cm = ConfigManager(str(config_file))
        assert cm.get_excel_path() == "20260527172302DataExport.xlsx"

    def test_additional_folders_read_write(self, tmp_config):
        """新增的四合一資料夾路徑設定應能正常讀寫與儲存"""
        # 測試讀取預設值
        assert tmp_config.get_excel_folder() == "."
        assert tmp_config.get_folder_institutional() == "."
        assert tmp_config.get_folder_daily_price() == "."
        assert tmp_config.get_folder_foreign_ownership() == "."

        # 測試寫入與回讀
        tmp_config.set_excel_folder("/path/warrant")
        tmp_config.set_folder_institutional("/path/institutional")
        tmp_config.set_folder_daily_price("/path/price")
        tmp_config.set_folder_foreign_ownership("/path/foreign")

        assert tmp_config.get_excel_folder() == "/path/warrant"
        assert tmp_config.get_folder_institutional() == "/path/institutional"
        assert tmp_config.get_folder_daily_price() == "/path/price"
        assert tmp_config.get_folder_foreign_ownership() == "/path/foreign"

    def test_batch_stock_folder_read_write(self, tmp_config):
        """測試 batch_stock_folder 設定之讀寫與預設值回傳"""
        # 測試預設值
        assert tmp_config.get_batch_stock_folder() == ""

        # 測試設定並讀回
        tmp_config.set_batch_stock_folder("/path/to/batch_folder")
        assert tmp_config.get_batch_stock_folder() == "/path/to/batch_folder"

