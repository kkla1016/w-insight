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
        "排名",                         # 名次排名
        "推薦評分",                     # 綜合評分（最前置以便排序）
        "代號", "名稱", "標的證券", "標的證券ROI%",
        "DELTA", "價內外程度", "剩餘期間(日)", "有效槓桿", "成本槓桿",
        "隱含波動", "歷史波動性", "IV_HV_ratio",
        "溢價比率%", "當日成交量", "未履約數", "流通在外比例(%)",
        "THETA", "VEGA", "履約價(元)", "權證收盤價(元)", "標的證券價格(元)",
    ]

    @staticmethod
    def calculate_score(row: pd.Series) -> float:
        """
        計算單支權證的綜合推薦評分（滿分 100 分）。

        評分維度：
        - Delta 適切度     ：25 分（越接近 0.5 分數越高）
        - 剩餘天期         ：20 分（天期越長越高，上限 180 天）
        - 有效槓桿         ：20 分（槓桿越高越好，上限 10x）
        - IV/HV 抄擺品質   ：20 分（IV/HV 越接近 1.0 越好）
        - 流動性（成交量） ：15 分（有成交量得基礎分，多越高）

        Args:
            row: DataFrame 的一列資料

        Returns:
            0~100 的浮點數評分
        """
        score = 0.0

        # ── Delta 適切度：25 分 ───────────────────────────────
        try:
            delta = float(row.get("DELTA", 0))
            # 讓 Delta=0.5 得滿分，越遠分數越低
            # 公式：25 * (1 - min(|delta - 0.5|, 0.5) / 0.5)
            delta_score = 25 * (1 - min(abs(delta - 0.5), 0.5) / 0.5)
            score += max(0, delta_score)
        except (TypeError, ValueError):
            pass

        # ── 剩餘天期：20 分 ──────────────────────────────────
        try:
            days = float(row.get("剩餘期間(日)", 0))
            # 180 天以上得滿分
            days_score = 20 * min(days / 180, 1.0)
            score += max(0, days_score)
        except (TypeError, ValueError):
            pass

        # ── 有效槓桿：20 分 ──────────────────────────────────
        try:
            lev = float(row.get("有效槓桿", 0))
            # 10x 以上得滿分
            lev_score = 20 * min(lev / 10.0, 1.0)
            score += max(0, lev_score)
        except (TypeError, ValueError):
            pass

        # ── IV/HV 抄擺品質：20 分 ────────────────────────────
        try:
            iv_hv = float(row.get("IV_HV_ratio", 1.0))
            # IV/HV 越接近 1.0 越好，超過 1.5 得 0 分
            if iv_hv <= 1.5:
                iv_score = 20 * (1 - min(abs(iv_hv - 1.0), 0.5) / 0.5)
                score += max(0, iv_score)
        except (TypeError, ValueError):
            pass

        # ── 流動性：15 分 ─────────────────────────────────────
        try:
            vol = float(row.get("當日成交量", 0))
            if vol > 0:
                import math
                # log10 計算，成交量 1000 張以上得滿分
                vol_score = 15 * min(math.log10(max(vol, 1)) / math.log10(1000), 1.0)
                score += max(0, vol_score)
        except (TypeError, ValueError):
            pass

        return round(score, 1)

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
        return self._select_output_cols(self._inject_scores(result))

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
        return self._select_output_cols(self._inject_scores(result))

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

        # 個股模式不再強制依 Delta 排序，改依「推薦評分」進行綜合排序
        # 這樣才能將成交量、天期等因素一併納入考量
        scored = self._inject_scores(filtered)
        return self._select_output_cols(scored.head(30))

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

        # 同樣改依「推薦評分」進行綜合排序
        scored = self._inject_scores(filtered)
        return self._select_output_cols(scored.head(30))

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
        """
        # 依股票名稱或代號搜尋，僅回傳完全包含關鍵字的資料
        q = str(query).strip()
        mask = (
            df["標的證券"].str.contains(q, na=False, case=False) |
            df["代號"].str.contains(q, na=False, case=False)
        )
        return df[mask].copy()

    # ──────────────────────────────────────────────────────────
    # V2 專業權證交易策略 (professional_warrant_trader_skill_v_2.md)
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def calculate_v2_score(row: pd.Series) -> float:
        """
        V2.0 系統總評分（滿分 100 分，近似版）
        A模組 (現股結構 25分): 以標的證券ROI%作為強度加分。
        B模組 (權證品質 35分): IV/HV (10分) + 基礎分(25分補償Spread等)。
        C模組 (爆發能力 20分): Delta 區間 (10分) + Gamma/Theta比 (10分)。
        D模組 (交易安全性 20分): 剩餘天期 (10分) + 流動性金額 (10分)。
        """
        score = 0.0
        
        # A 模組：現股結構 (25分) -> 基礎分 15 + ROI加分 (最高10)
        roi = row.get("標的證券ROI%", 0)
        roi_score = 10 if roi > 4 else (7 if roi > 2 else (4 if roi > 0 else 0))
        score += 15 + roi_score

        # B 模組：權證品質 (35分) -> 基礎分 25 + IV/HV (最高10)
        iv_hv = row.get("IV_HV_ratio", 1.0)
        if pd.isna(iv_hv):
            iv_score = 5
        elif 0.8 <= iv_hv <= 1.2:
            iv_score = 10
        elif iv_hv <= 1.4:
            iv_score = 6
        elif iv_hv <= 1.6:
            iv_score = 3
        else:
            iv_score = 0
        score += 25 + iv_score

        # C 模組：爆發能力 (20分)
        # C1. Delta 區間 (10分)
        delta = row.get("DELTA", 0)
        if pd.isna(delta):
            delta = 0
        delta = abs(delta) # 轉正數
        if 0.25 <= delta <= 0.45:
            d_score = 10
        elif 0.45 < delta <= 0.65:
            d_score = 8
        elif 0.15 <= delta < 0.25:
            d_score = 6
        elif delta > 0.70:
            d_score = 3
        else:
            d_score = 2
        score += d_score

        # C2. Gamma/Theta (10分)
        gamma = row.get("GAMMA", 0)
        theta = row.get("THETA", -1) # 通常是負數
        gamma = 0 if pd.isna(gamma) else gamma
        theta = -1 if pd.isna(theta) or theta == 0 else theta
        
        # Gamma/abs(Theta) 比值，越大越好
        gt_ratio = gamma / abs(theta)
        if gt_ratio > 50:
            gt_score = 10
        elif gt_ratio > 20:
            gt_score = 6
        else:
            gt_score = 2
        score += gt_score

        # D 模組：交易安全性 (20分)
        # D1. 剩餘天期 (10分)
        days = row.get("剩餘期間(日)", 0)
        if days >= 90:
            days_score = 10
        elif days >= 60:
            days_score = 7
        elif days >= 45:
            days_score = 4
        else:
            days_score = 0
        score += days_score

        # D2. 流動性 (10分) - 成交金額 (成交量 * 收盤價 * 1000)
        vol = row.get("當日成交量", 0)
        price = row.get("權證收盤價(元)", 1)
        amount = vol * price * 1000
        if amount > 3000000:
            amount_score = 10
        elif amount >= 1000000:
            amount_score = 7
        elif amount >= 500000:
            amount_score = 4
        else:
            amount_score = 0
        score += amount_score

        return round(score, 1)

    def filter_v2_class_a(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        V2.0 A級：主力攻擊型 (S級 85-100 / A級 75-84)
        """
        # 基本排除死亡名單
        mask = (
            (df["IV_HV_ratio"] <= 1.8) &
            (df["剩餘期間(日)"] >= 30)
        )
        filtered = df[mask].copy()
        if filtered.empty:
            return filtered
        
        # 計算分數
        filtered["推薦評分"] = filtered.apply(self.calculate_v2_score, axis=1)
        # S級與A級：分數 >= 75
        result = filtered[filtered["推薦評分"] >= 75].copy()
        result = result.sort_values("推薦評分", ascending=False).reset_index(drop=True)
        return self._select_output_cols(result.head(30))

    def filter_v2_class_b(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        V2.0 B級：穩健趨勢型 (B級 60-74)
        """
        # 基本排除死亡名單
        mask = (
            (df["IV_HV_ratio"] <= 1.8) &
            (df["剩餘期間(日)"] >= 30)
        )
        filtered = df[mask].copy()
        if filtered.empty:
            return filtered

        # 計算分數
        filtered["推薦評分"] = filtered.apply(self.calculate_v2_score, axis=1)
        # B級：分數 60 ~ 74
        result = filtered[(filtered["推薦評分"] >= 60) & (filtered["推薦評分"] < 75)].copy()
        result = result.sort_values("推薦評分", ascending=False).reset_index(drop=True)
        return self._select_output_cols(result.head(30))

    def get_unique_stocks(self, df: pd.DataFrame) -> list[str]:
        """回傳所有唯一的標的證券名稱清單，供自動補全使用"""
        if "標的證券" in df.columns:
            return sorted(df["標的證券"].dropna().unique().tolist())
        return []

    def _inject_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        對第一欄注入「推薦評分」欄，並依評分倒序重新排列。
        評分後加入排名後缀（第1~3名加 ★ 標記）。

        Args:
            df: 筛選後的 DataFrame

        Returns:
            帶有 推薦評分 欄的新 DataFrame
        """
        if df.empty:
            return df
        result = df.copy()
        # 計算每列的評分
        result["推薦評分"] = result.apply(self.calculate_score, axis=1)
        # 依評分倒序排列
        result = result.sort_values("推薦評分", ascending=False).reset_index(drop=True)
        return result

    def _select_output_cols(
        self, df: pd.DataFrame, cols: list[str] | None = None
    ) -> pd.DataFrame:
        """只保留存在且在指定清單中的欄位，避免 KeyError"""
        target = cols if cols is not None else self.OUTPUT_COLS
        
        # 若需要輸出排名，動態產生名次
        if not df.empty and "排名" in target and "排名" not in df.columns:
            df = df.copy()
            df.insert(0, "排名", range(1, len(df) + 1))
            
        available = [c for c in target if c in df.columns]
        return df[available].reset_index(drop=True)
