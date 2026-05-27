"""
WarrantFilter 單元測試
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import pandas as pd
import numpy as np
from models.warrant_filter import WarrantFilter


@pytest.fixture
def flt():
    return WarrantFilter()


@pytest.fixture
def base_df():
    """模擬預處理後的 DataFrame"""
    return pd.DataFrame({
        "代號": ["A001", "A002", "A003", "A004", "A005"],
        "名稱": ["台積電W1", "聯發科W2", "鴻海W3", "台積電W4", "聯電W5"],
        "標的證券": ["台積電", "聯發科", "鴻海", "台積電", "聯電"],
        "DELTA": [0.50, 0.55, 0.15, 0.20, 0.45],
        "剩餘期間(日)": [100, 110, 80, 90, 95],
        "有效槓桿": [6.5, 7.2, 10.0, 8.5, 5.5],
        "成本槓桿": [5.0, 5.5, 8.0, 7.0, 4.5],
        "IV_HV_ratio": [1.10, 1.20, 1.05, 1.25, 1.60],
        "當日成交量": [50, 30, 15, 100, 25],
        "標的證券ROI%": [2.0, 3.0, 2.5, 3.5, 1.0],
        "溢價比率%": [5.0, 4.0, 8.0, 6.0, 3.0],
        "隱含波動": [0.35, 0.42, 0.30, 0.38, 0.55],
        "歷史波動性": [0.30, 0.35, 0.28, 0.30, 0.34],
        "未履約數": [5000, 3000, 2000, 4000, 1500],
        "流通在外比例(%)": [60.0, 45.0, 30.0, 55.0, 20.0],
        "THETA": [-0.05, -0.03, -0.07, -0.04, -0.06],
        "VEGA": [0.10, 0.12, 0.08, 0.11, 0.09],
        "履約價(元)": [900, 1000, 100, 950, 45],
        "權證收盤價(元)": [0.52, 0.65, 0.30, 0.48, 0.25],
    })


@pytest.fixture
def phase1_params():
    return {
        "delta_min": 0.40, "delta_max": 0.60,
        "remaining_days_min": 90,
        "iv_hv_min": 0.70, "iv_hv_max": 1.30,
        "min_volume": 20,
        "min_underlying_roi": 1.5,
    }


@pytest.fixture
def phase2_params():
    return {
        "delta_min": 0.05, "delta_max": 0.30,
        "remaining_days_min": 60, "remaining_days_max": 120,
        "min_leverage": 5.0,
        "iv_hv_max": 1.30,
        "min_volume": 10,
        "min_underlying_roi": 2.0,
    }


class TestWarrantFilter:
    """WarrantFilter 測試集"""

    def test_phase1_returns_correct_rows(self, flt, base_df, phase1_params):
        """階段一應只回傳 Delta 0.4~0.6、天期>90、IV/HV<1.3 等條件的行"""
        result = flt.filter_phase1(base_df, phase1_params)
        # A001: Delta=0.5, 天期=100, IV/HV=1.10, 量=50, ROI=2.0 → 符合
        # A002: Delta=0.55, 天期=110, IV/HV=1.20, 量=30, ROI=3.0 → 符合
        # A005: IV/HV=1.60 → 不符合
        assert len(result) == 2
        for _, row in result.iterrows():
            assert 0.40 <= row["DELTA"] <= 0.60
            assert row["剩餘期間(日)"] > 90
            assert row["IV_HV_ratio"] <= 1.30
            assert row["當日成交量"] >= 20
            assert row["標的證券ROI%"] > 1.5

    def test_phase1_sorted_by_score_desc(self, flt, base_df, phase1_params):
        """階段一結果應依推薦評分降序排列，且包含推薦評分欄"""
        result = flt.filter_phase1(base_df, phase1_params)
        # 驗證推薦評分欄存在
        assert "推薦評分" in result.columns
        # 驗證依推薦評分降序排列
        scores = result["推薦評分"].tolist()
        assert scores == sorted(scores, reverse=True), f"評分未降序排列: {scores}"


    def test_phase2_returns_correct_rows(self, flt, base_df, phase2_params):
        """階段二應只回傳 Delta 0.05~0.30、天期60~120、槓桿>=5 等條件的行"""
        result = flt.filter_phase2(base_df, phase2_params)
        # A003: Delta=0.15, 天期=80, 槓桿=10, IV/HV=1.05, 量=15, ROI=2.5 → 符合
        # A004: Delta=0.20, 天期=90, 槓桿=8.5, IV/HV=1.25, 量=100, ROI=3.5 → 符合
        assert len(result) == 2
        for _, row in result.iterrows():
            assert 0.05 <= row["DELTA"] <= 0.30
            assert 60 <= row["剩餘期間(日)"] <= 120
            assert row["有效槓桿"] >= 5.0
            assert row["IV_HV_ratio"] <= 1.30

    def test_phase2_sorted_by_leverage_desc(self, flt, base_df, phase2_params):
        """階段二結果應依有效槓桿降序排列"""
        result = flt.filter_phase2(base_df, phase2_params)
        leverages = result["有效槓桿"].tolist()
        assert leverages == sorted(leverages, reverse=True)

    def test_detect_iv_warnings(self, flt, base_df):
        """IV 警示應正確偵測 IV/HV > 1.5 的標的"""
        result = flt.detect_iv_warnings(base_df, threshold=1.5)
        # A005: IV/HV=1.60, 量=25, ROI=1.0 → ROI 不符 2.0，不符合
        # 所以結果應為 0 筆（A005 的 ROI=1.0 < 2.0）
        assert len(result) == 0

    def test_detect_iv_warnings_with_high_roi(self, flt):
        """IV/HV 高且 ROI 足夠的標的應出現在警示清單"""
        df = pd.DataFrame({
            "代號": ["B001"], "名稱": ["高風險W"],
            "標的證券": ["某股"],
            "DELTA": [0.3], "剩餘期間(日)": [90],
            "有效槓桿": [8.0], "成本槓桿": [6.0],
            "IV_HV_ratio": [2.0],   # > 1.5 → 警示
            "當日成交量": [100],
            "標的證券ROI%": [3.0],  # > 2.0 → 符合警示條件
            "溢價比率%": [5.0],
            "隱含波動": [0.60], "歷史波動性": [0.30],
            "未履約數": [1000], "流通在外比例(%)": [50.0],
            "THETA": [-0.05], "VEGA": [0.10],
            "履約價(元)": [100], "權證收盤價(元)": [0.50],
        })
        result = flt.detect_iv_warnings(df, threshold=1.5)
        assert len(result) == 1

    def test_search_by_stock_matches_partial(self, flt, base_df):
        """股票搜尋應支援部分匹配"""
        result = flt.search_by_stock(base_df, "台積電")
        assert len(result) == 2  # A001 和 A004

    def test_search_by_stock_empty_query(self, flt, base_df):
        """空白搜尋應回傳全部資料"""
        result = flt.search_by_stock(base_df, "")
        assert len(result) == len(base_df)

    def test_get_unique_stocks(self, flt, base_df):
        """應回傳唯一的標的證券名稱清單"""
        stocks = flt.get_unique_stocks(base_df)
        assert "台積電" in stocks
        assert "聯發科" in stocks
        assert len(stocks) == len(set(base_df["標的證券"]))
