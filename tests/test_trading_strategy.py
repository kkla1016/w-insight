"""
TradingStrategy 單元測試
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from models.trading_strategy import TradingStrategy


@pytest.fixture
def strategy():
    return TradingStrategy()


class TestTradingStrategy:
    """TradingStrategy 測試集"""

    def test_phase1_analysis_not_empty(self, strategy):
        """階段一解析文字不應為空"""
        text = strategy.get_phase1_analysis()
        assert len(text) > 0
        assert "Delta" in text or "delta" in text.lower() or "0.5" in text

    def test_phase2_analysis_not_empty(self, strategy):
        """階段二解析文字不應為空"""
        text = strategy.get_phase2_analysis()
        assert len(text) > 0
        assert "Gamma" in text or "槓桿" in text

    def test_phase1_exit_discipline_contains_stopwords(self, strategy):
        """階段一出場紀律應包含停損與停利"""
        text = strategy.get_phase1_exit_discipline()
        assert "停損" in text
        assert "停利" in text

    def test_phase2_exit_discipline_contains_stopwords(self, strategy):
        """階段二出場紀律應包含停損與停利"""
        text = strategy.get_phase2_exit_discipline()
        assert "停損" in text
        assert "停利" in text

    def test_iv_risk_level_normal(self, strategy):
        """IV/HV ≤ 1.3 應回傳正常"""
        assert strategy.get_iv_risk_level(1.0) == "正常"
        assert strategy.get_iv_risk_level(1.30) == "正常"

    def test_iv_risk_level_caution(self, strategy):
        """1.3 < IV/HV ≤ 1.5 應回傳注意"""
        assert strategy.get_iv_risk_level(1.31) == "注意"
        assert strategy.get_iv_risk_level(1.50) == "注意"

    def test_iv_risk_level_high_risk(self, strategy):
        """IV/HV > 1.5 應回傳高風險"""
        assert strategy.get_iv_risk_level(1.51) == "高風險"
        assert strategy.get_iv_risk_level(3.0) == "高風險"

    def test_greek_tooltip_delta(self, strategy):
        """DELTA Tooltip 應含關鍵說明字"""
        tip = strategy.get_greek_tooltip("DELTA")
        assert "Delta" in tip or "連動" in tip

    def test_greek_tooltip_unknown(self, strategy):
        """未知欄位 Tooltip 應回傳欄位名稱本身"""
        tip = strategy.get_greek_tooltip("UNKNOWN_COL")
        assert tip == "UNKNOWN_COL"

    def test_report_title_not_empty(self, strategy):
        """報告標題不應為空"""
        assert len(strategy.get_report_title()) > 0

    def test_report_subtitle_with_stock(self, strategy):
        """含標的名稱的副標題應包含股票名稱"""
        subtitle = strategy.get_report_subtitle("台積電", "2026/05/27")
        assert "台積電" in subtitle
        assert "2026/05/27" in subtitle

    def test_report_subtitle_without_stock(self, strategy):
        """無標的名稱時應顯示全市場字樣"""
        subtitle = strategy.get_report_subtitle("", "2026/05/27")
        assert "全市場" in subtitle
