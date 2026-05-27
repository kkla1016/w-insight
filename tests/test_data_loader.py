"""
DataLoader 單元測試
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import pandas as pd
import numpy as np
from models.data_loader import DataLoader


@pytest.fixture
def loader():
    """建立 DataLoader 實例"""
    return DataLoader()


@pytest.fixture
def sample_df():
    """建立測試用 DataFrame（模擬 Excel 匯出格式）"""
    return pd.DataFrame({
        "代號": ["30012", "30021", "30999"],
        "名稱": ["台積電凱基58購01", "台玻群益56購01", "00050元大購01"],
        "日期": ["2026/05/27", "2026/05/27", "2026/05/27"],
        "DELTA": ["0.52", "0.45", "0.35"],
        "GAMMA": ["0.01", "0.02", "0.03"],
        "VEGA": ["0.10", "0.12", "0.08"],
        "THETA": ["-0.05", "-0.03", "-0.07"],
        "RHO": ["0.01", "0.01", "0.01"],
        "剩餘期間(日)": ["120", "95", "100"],
        "有效槓桿": ["8.5", "6.2", "4.0"],
        "成本槓桿": ["7.0", "5.5", "3.5"],
        "當日成交量": ["150", "30", "500"],
        "溢價比率%": ["5.2", "3.1", "2.0"],
        "隱含波動": ["0.35", "0.42", "0.30"],
        "歷史波動性": ["0.30", "0.35", "0.28"],
        "標的證券ROI%": ["2.5", "1.8", "1.2"],
        "未履約數": ["5000", "3000", "2000"],
        "流通在外比例(%)": ["60.0", "45.0", "30.0"],
        "標的證券": ["2330", "1802", "00050"],
        "權證ROI(%)": ["5.0", "3.0", "2.0"],
        "權證收盤價(元)": ["0.52", "0.43", "0.38"],
        "履約價(元)": ["900", "28", "150"],
        "標的證券價格(元)": ["850", "25", "145"],
        "權證高估%": ["2.0", "1.5", "1.0"],
    })


class TestDataLoader:
    """DataLoader 測試集"""

    def test_convert_numeric(self, loader, sample_df):
        """數值欄位應正確轉換為數值型態（int64 或 float64 均可接受）"""
        result = loader._convert_numeric(sample_df)
        assert pd.api.types.is_numeric_dtype(result["DELTA"])
        assert pd.api.types.is_numeric_dtype(result["剩餘期間(日)"])
        assert pd.api.types.is_numeric_dtype(result["有效槓桿"])

    def test_calculate_iv_hv(self, loader, sample_df):
        """IV/HV 比率計算應正確"""
        df = loader._convert_numeric(sample_df)
        result = loader._calculate_iv_hv(df)
        assert "IV_HV_ratio" in result.columns
        # 0.35 / 0.30 ≈ 1.167
        assert abs(result.iloc[0]["IV_HV_ratio"] - (0.35 / 0.30)) < 0.001

    def test_filter_call_warrants(self, loader, sample_df):
        """只應保留名稱含「購」字的認購權證"""
        result = loader._filter_call_warrants(sample_df)
        assert len(result) == 3  # 三筆都含「購」
        assert all("購" in n for n in result["名稱"])

    def test_exclude_etf(self, loader, sample_df):
        """應排除 ETF 標的（00050）"""
        result = loader._exclude_etf(sample_df)
        assert len(result) == 2  # 排除 00050 那筆
        assert "00050" not in result["標的證券"].values

    def test_preprocess_full_pipeline(self, loader, sample_df):
        """完整預處理後應有正確欄位與筆數"""
        result = loader.preprocess(sample_df)
        assert "IV_HV_ratio" in result.columns
        assert len(result) == 2  # 排除 ETF 後剩 2 筆

    def test_file_not_found(self, loader):
        """不存在的檔案應拋出 FileNotFoundError"""
        with pytest.raises(FileNotFoundError):
            loader.load_excel("not_exist_file.xlsx")

    def test_iv_hv_zero_denominator(self, loader):
        """歷史波動性為 0 時 IV/HV 應為 NaN（避免除以零）"""
        df = pd.DataFrame({
            "隱含波動": [0.30],
            "歷史波動性": [0.0],
        })
        result = loader._calculate_iv_hv(df)
        assert pd.isna(result.iloc[0]["IV_HV_ratio"])
