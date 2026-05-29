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


class TestReportGeneratorChips:
    """測試 ReportGenerator 籌碼與技術面數據檢索 (本機優先與網路降級)"""

    @pytest.fixture
    def generator(self, tmp_path):
        from models.report_generator import ReportGenerator
        from utils.config_manager import ConfigManager
        # 使用 tmp_path 建立測試隔離的臨時設定檔，避免單元測試覆寫實體的 config.json
        test_config_file = tmp_path / "test_config.json"
        gen = ReportGenerator()
        gen._config = ConfigManager(str(test_config_file))
        return gen

    def test_web_fallback_data(self, generator):
        """測試無本機 Excel 檔案時應自動降級至網路搜尋，並顯示網路標記"""
        # 故意將三個目錄路徑設為不存在的目錄，強迫其降級
        generator._config.set_folder_daily_price("/non_existent_folder_1")
        generator._config.set_folder_institutional("/non_existent_folder_2")
        generator._config.set_folder_foreign_ownership("/non_existent_folder_3")

        data = generator._get_chips_and_price_data("南茂 (8150)")
        assert data["source"] == "網路搜尋"
        assert len(data["avg_price"]) > 0
        assert len(data["net_buy"]) > 0
        assert len(data["foreign_ratio"]) > 0

    def test_local_excel_parsing(self, tmp_path, generator):
        """測試當本機有 Excel 資料時，應精確匹配並讀出資料，且標記為本機資料庫"""
        import pandas as pd
        
        # 1. 建立暫存目錄與 Excel
        dir_price = tmp_path / "price"
        dir_inst = tmp_path / "inst"
        dir_fore = tmp_path / "fore"

        dir_price.mkdir()
        dir_inst.mkdir()
        dir_fore.mkdir()

        df_price = pd.DataFrame({
            "證券代號": ["8150", "2330"],
            "證券簡稱": ["南茂", "台積電"],
            "均價": [38.50, 580.00]
        })
        df_inst = pd.DataFrame({
            "證券代碼": [8150, 2330],
            "三大法人今日買賣超(張)": [1234, -5678]
        })
        df_fore = pd.DataFrame({
            "代碼": ["8150", "2330"],
            "外資持股比率(%)": [28.45, 75.20]
        })

        price_file = dir_price / "price.xlsx"
        inst_file = dir_inst / "inst.xlsx"
        fore_file = dir_fore / "fore.xlsx"

        df_price.to_excel(price_file, index=False)
        df_inst.to_excel(inst_file, index=False)
        df_fore.to_excel(fore_file, index=False)

        # 2. 配置路徑至 Config
        generator._config.set_folder_daily_price(str(dir_price))
        generator._config.set_folder_institutional(str(dir_inst))
        generator._config.set_folder_foreign_ownership(str(dir_fore))

        # 3. 測試讀取與智慧匹配
        df_p1 = pd.DataFrame({"標的證券": ["8150 南茂"]})
        local_price = generator._fetch_stock_data_from_excel(str(price_file), "8150 南茂", ["均價", "收盤", "價格", "均"])
        local_inst = generator._fetch_stock_data_from_excel(str(inst_file), "8150 南茂", ["買賣超", "法人", "三大法人", "張數", "今日"])
        local_fore = generator._fetch_stock_data_from_excel(str(fore_file), "8150 南茂", ["持股", "比例", "外資", "百分比", "%"])
        
        print(f"DEBUG - local_price: {local_price}")
        print(f"DEBUG - local_inst: {local_inst}")
        print(f"DEBUG - local_fore: {local_fore}")

        data = generator._get_chips_and_price_data("南茂", df_p1)
        assert data["source"] == "本機資料庫"
        assert "38.50" in data["avg_price"]
        assert "+1234" in data["net_buy"]
        assert "28.45" in data["foreign_ratio"]

    def test_comprehensive_comparison_table_generation(self, generator):
        """測試綜合大評比與排名整理表格的生成邏輯，確認能處理前3名聯集與公式計算價內外"""
        import pandas as pd
        
        # 建立測試用的 DataFrame：配置 4 筆以驗證只提取前 3 名
        phase1 = pd.DataFrame([
            {"代號": "03001P", "名稱": "南茂凱基01", "隱含波動": 45.2, "標的證券價格(元)": 100.0, "履約價(元)": 90.0,
             "剩餘期間(日)": 115, "有效槓桿": 5.8, "流通在外比例(%)": 25.4, "未履約數": 500,
             "當日成交量": 120, "推薦評分": 85.5, "排名": 1},
            {"代號": "03002P", "名稱": "南茂凱基02", "隱含波動": 45.2, "標的證券價格(元)": 90.0, "履約價(元)": 100.0,
             "剩餘期間(日)": 115, "有效槓桿": 5.8, "流通在外比例(%)": 25.4, "未履約數": 500,
             "當日成交量": 120, "推薦評分": 84.5, "排名": 2},
            {"代號": "03003P", "名稱": "南茂凱基03", "隱含波動": 45.2, "標的證券價格(元)": 100.0, "履約價(元)": 100.0,
              "剩餘期間(日)": 115, "有效槓桿": 5.8, "流通在外比例(%)": 25.4, "未履約數": 500,
              "當日成交量": 120, "推薦評分": 83.5, "排名": 3},
            # 第 4 筆：應被 top 3 過濾掉
            {"代號": "03004P", "名稱": "南茂凱基04", "隱含波動": 45.2, "標的證券價格(元)": 100.0, "履約價(元)": 100.0,
              "剩餘期間(日)": 115, "有效槓桿": 5.8, "流通在外比例(%)": 25.4, "未履約數": 500,
              "當日成交量": 120, "推薦評分": 82.5, "排名": 4}
        ])
        
        # 建立 V2 主力 (class_a)，只有 1 筆且與 phase1 重複，用以驗證去重
        class_a = pd.DataFrame([{
            "代號": "03001P", "名稱": "南茂凱基01", "隱含波動": 45.2, "標的證券價格(元)": 100.0, "履約價(元)": 90.0,
            "剩餘期間(日)": 115, "有效槓桿": 5.8, "流通在外比例(%)": 25.4, "未履約數": 500,
            "當日成交量": 120, "推薦評分": 85.5, "排名": 2
        }])
        
        styles = generator._build_styles()
        elements = generator._build_comprehensive_comparison_table(
            styles=styles,
            stock_name="8150 南茂",
            phase1=phase1,
            class_a=class_a
        )
        
        # 驗證返回了 Flowables 列表且包含 Table
        assert len(elements) > 0
        from reportlab.platypus import Table
        tables = [el for el in elements if isinstance(el, Table)]
        assert len(tables) == 1
        
        # 驗證 Table 資料內容：有 1 個表頭行 + 3 個資料行 = 4 行 (第 4 筆被過濾，第 1 筆被去重)
        tbl_data = tables[0]._cellvalues
        assert len(tbl_data) == 4
        
        # 驗證價內外公式自主計算結果
        # 第 1 筆 (03001P): (100 - 90)/90 = +11.11% => 價內 11.1%
        # 第 2 筆 (03002P): (90 - 100)/100 = -10.0% => 價外 10.0%
        # 第 3 筆 (03003P): (100 - 100)/100 = 0.0% => 價內 0.0%
        rows_text = []
        for row in tbl_data[1:]:
            rows_text.append([c.text for c in row])
            
        moneyness_vals = [r[2] for r in rows_text]
        assert any("價內 11.1%" in val for val in moneyness_vals)
        assert any("價外 10.0%" in val for val in moneyness_vals)
        assert any("價內 0.0%" in val for val in moneyness_vals)


