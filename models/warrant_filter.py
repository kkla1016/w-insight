"""
權證篩選器模組
實作「頂尖權證交易員」兩階段選股策略的篩選邏輯
"""

import pandas as pd


class WarrantFilter:
    """
    實作「頂尖權證交易員skill」兩階段選股篩選邏輯。
    遵循 SRP，僅負責各類條件的篩選運算。

    兩種運作模式：
    - 全市場模式：用嚴格門檻篩選出最優質標的（無搜尋關鍵字時）
    - 個股分析模式：搜尋特定股票時，對該股所有權證做排名推薦
    """

    # 輸出欄位清單（報表所需欄位）
    OUTPUT_COLS = [
        "代號", "名稱", "標的證券", "標的證券ROI%",
        "DELTA", "剩餘期間(日)", "有效槓桿", "成本槓桿",
        "隱含波動", "歷史波動性", "IV_HV_ratio",
        "溢價比率%", "當日成交量", "未履約數", "流通在外比例(%)",
        "THETA", "VEGA", "履約價(元)", "權證收盤價(元)",
    ]

    def filter_phase1(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """
        【階段一】突破起漲 — 安全建倉篩選
        策略：進可攻、退可守，選價平附近長天期權證。

        Args:
            df: 預處理後的 DataFrame
            params: 階段一篩選參數（來自 config.json）

        Returns:
            符合條件的 DataFrame，依標的ROI% 及成交量降序排列
        """
        mask = (
            (df["DELTA"] >= params["delta_min"]) &
            (df["DELTA"] <= params["delta_max"]) &
            (df["剩餘期間(日)"] > params["remaining_days_min"]) &
            (df["IV_HV_ratio"] >= params["iv_hv_min"]) &
            (df["IV_HV_ratio"] <= params["iv_hv_max"]) &
            (df["當日成交量"] >= params["min_volume"]) &
            (df["標的證券ROI%"] > params["min_underlying_roi"])
        )
        result = df[mask].copy()
        result = result.sort_values(
            ["標的證券ROI%", "當日成交量"],
            ascending=[False, False]
        )
        return self._select_output_cols(result)

    def filter_phase2(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """
        【階段二】主升段飆漲 — 極致動能加碼篩選
        策略：利用 Gamma 加速特性，買微價外高槓桿。

        Args:
            df: 預處理後的 DataFrame
            params: 階段二篩選參數（來自 config.json）

        Returns:
            符合條件的 DataFrame，依有效槓桿及標的ROI% 降序排列
        """
        mask = (
            (df["DELTA"] >= params["delta_min"]) &
            (df["DELTA"] <= params["delta_max"]) &
            (df["剩餘期間(日)"] >= params["remaining_days_min"]) &
            (df["剩餘期間(日)"] <= params["remaining_days_max"]) &
            (df["有效槓桿"] >= params["min_leverage"]) &
            (df["IV_HV_ratio"] <= params["iv_hv_max"]) &
            (df["當日成交量"] >= params["min_volume"]) &
            (df["標的證券ROI%"] > params["min_underlying_roi"])
        )
        result = df[mask].copy()
        result = result.sort_values(
            ["有效槓桿", "標的證券ROI%"],
            ascending=[False, False]
        )
        return self._select_output_cols(result)

    def detect_iv_warnings(self, df: pd.DataFrame, threshold: float = 1.5) -> pd.DataFrame:
        """
        偵測 IV 異常（造市商可能惡意調高 IV）的高風險標的。

        Args:
            df: 預處理後的 DataFrame
            threshold: IV/HV 警示門檻值，預設 1.5

        Returns:
            IV 異常標的的 DataFrame，依 IV_HV_ratio 降序排列
        """
        mask = (
            (df["IV_HV_ratio"] > threshold) &
            (df["當日成交量"] >= 10) &
            (df["標的證券ROI%"] > 2.0)
        )
        result = df[mask].copy()
        result = result.sort_values("IV_HV_ratio", ascending=False)

        warning_cols = [
            "代號", "名稱", "標的證券", "標的證券ROI%",
            "IV_HV_ratio", "隱含波動", "歷史波動性",
            "有效槓桿", "當日成交量",
        ]
        return self._select_output_cols(result, warning_cols)

    def filter_stock_phase1(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        【個股分析模式 - 階段一】安全建倉推薦
        當使用者搜尋特定股票時使用，放寬 Delta 限制，
        依「天期 ≥ 60 天、IV/HV ≤ 1.3、成交量 ≥ 1、Delta 由高到低」排序。
        策略：優先選較接近平值、天期較長的權證（風險適中）。

        Args:
            df: 已依股票名稱搜尋過的 DataFrame（僅含該標的）

        Returns:
            推薦排序後的 DataFrame（最多 30 筆）
        """
        # 基本過濾：去除完全無流動性及 IV 異常
        mask = (
            (df["剩餘期間(日)"] >= 60) &
            (df["IV_HV_ratio"] <= 1.3) &
            (df["當日成交量"] >= 1)
        )
        filtered = df[mask].copy()

        # 若過濾後太少，放寬條件
        if len(filtered) < 5:
            mask_relax = (
                (df["剩餘期間(日)"] >= 30) &
                (df["IV_HV_ratio"] <= 1.5)
            )
            filtered = df[mask_relax].copy()

        # 依 DELTA 由大到小（越接近平值越好），再依成交量
        filtered = filtered.sort_values(
            ["DELTA", "當日成交量"],
            ascending=[False, False]
        )
        return self._select_output_cols(filtered.head(30))

    def filter_stock_phase2(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        【個股分析模式 - 階段二】動能加碼推薦
        當使用者搜尋特定股票時使用，放寬槓桿門檻，
        依「Delta 0.05~0.30、有效槓桿由高到低」排序。
        策略：尋找高槓桿微價外權證，追求 Gamma 加速效果。

        Args:
            df: 已依股票名稱搜尋過的 DataFrame（僅含該標的）

        Returns:
            推薦排序後的 DataFrame（最多 30 筆）
        """
        # 微價外高槓桿：Delta 0.03~0.30、天期 ≥ 30 天
        mask = (
            (df["DELTA"] >= 0.03) &
            (df["DELTA"] <= 0.30) &
            (df["剩餘期間(日)"] >= 30) &
            (df["IV_HV_ratio"] <= 1.3) &
            (df["當日成交量"] >= 1)
        )
        filtered = df[mask].copy()

        # 若結果不足，放寬至所有 Delta < 0.4 的權證
        if len(filtered) < 5:
            mask_relax = (
                (df["DELTA"] < 0.4) &
                (df["剩餘期間(日)"] >= 20)
            )
            filtered = df[mask_relax].copy()

        # 依有效槓桿由高到低，再依 Delta
        filtered = filtered.sort_values(
            ["有效槓桿", "DELTA"],
            ascending=[False, False]
        )
        return self._select_output_cols(filtered.head(30))

    def detect_stock_iv_warnings(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        【個股分析模式 - IV 警示】對個股所有權證進行 IV 異常檢測。
        門檻放寬到 IV/HV > 1.1 即標記（個股分析更要求精準）。

        Args:
            df: 已依股票名稱搜尋過的 DataFrame（僅含該標的）

        Returns:
            IV 偏高的權證，供使用者迴避
        """
        # 個股模式：IV/HV > 1.1 即列入注意
        mask = (df["IV_HV_ratio"] > 1.1)
        result = df[mask].copy()
        result = result.sort_values("IV_HV_ratio", ascending=False)

        warning_cols = [
            "代號", "名稱", "標的證券", "標的證券ROI%",
            "IV_HV_ratio", "隱含波動", "歷史波動性",
            "有效槓桿", "當日成交量",
        ]
        return self._select_output_cols(result, warning_cols)

    def search_by_stock(self, df: pd.DataFrame, query: str) -> pd.DataFrame:
        """
        依標的證券名稱或代號進行模糊搜尋。

        Args:
            df: 預處理後的 DataFrame
            query: 搜尋關鍵字（支援部分匹配）

        Returns:
            匹配的 DataFrame，空字串時回傳原始 df
        """
        if not query or not query.strip():
            return df
        q = query.strip()
        # 同時比對標的證券名稱與代號
        mask = (
            df["標的證券"].str.contains(q, na=False, case=False) |
            df["代號"].str.contains(q, na=False, case=False)
        )
        return df[mask].copy()

    def get_unique_stocks(self, df: pd.DataFrame) -> list[str]:
        """回傳所有唯一的標的證券名稱清單，供自動補全使用"""
        if "標的證券" in df.columns:
            return sorted(df["標的證券"].dropna().unique().tolist())
        return []

    def _select_output_cols(
        self, df: pd.DataFrame, cols: list[str] | None = None
    ) -> pd.DataFrame:
        """只保留存在且在指定清單中的欄位，避免 KeyError"""
        target = cols if cols is not None else self.OUTPUT_COLS
        available = [c for c in target if c in df.columns]
        return df[available].reset_index(drop=True)
