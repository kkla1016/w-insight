"""
交易策略文字模組
將「頂尖權證交易員skill」的策略解析、出場紀律、希臘字母說明
封裝為 Python 類別，供 PDF 報告與 GUI Tooltip 使用。
"""


class TradingStrategy:
    """
    封裝「頂尖權證交易員」skill 的所有策略文字。
    提供 PDF 報告內容與 GUI 工具提示文字。
    """

    # ---------- 階段一：突破起漲 ----------

    def get_phase1_analysis(self) -> str:
        """回傳階段一建倉策略的交易員視角解析文字"""
        return (
            "【交易員視角】突破起漲 — 安全建倉\n"
            "剛突破的股票容易遇到「回測頸線」或洗盤修正。\n"
            "因此選擇 Delta 約 0.5 的價平附近權證（連動性佳），\n"
            "搭配 90 天以上的長天期（降低 Theta 時間價值消耗），\n"
            "確保即使股票短暫整理，權證也不會因時間損耗大幅虧損。\n"
            "IV/HV 控制在 0.70~1.30 之間，避免遭遇惡意調高 IV 的造市商。"
        )

    def get_phase1_exit_discipline(self) -> str:
        """回傳階段一出場紀律文字"""
        return (
            "【出場紀律 — 階段一】\n"
            "◆ 停損：跌破突破 K 棒低點，或權證虧損達 15% 即出場\n"
            "◆ 停利：股價站穩後，跌破 10 日均線時獲利出場（移動停利）"
        )

    # ---------- 階段二：主升段飆漲 ----------

    def get_phase2_analysis(self) -> str:
        """回傳階段二主升段策略的交易員視角解析文字"""
        return (
            "【交易員視角】主升段飆漲 — 極致動能加碼\n"
            "趨勢確認後，目標是買下「Gamma 加速度」。\n"
            "選擇價外 10%~20% 的微價外權證（Delta 0.05~0.30），\n"
            "當現股持續飆漲進入價內時，漲幅呈幾何級數噴發。\n"
            "天期 60~120 天，承受稍高的 Theta 換取更高的實質槓桿（≥5倍）。\n"
            "絕對迴避不報價或買賣價差極大的劣質造市商。"
        )

    def get_phase2_exit_discipline(self) -> str:
        """回傳階段二出場紀律文字"""
        return (
            "【出場紀律 — 階段二】\n"
            "◆ 停損：單筆權證最大虧損 20%，嚴格執行\n"
            "◆ 停利：跌破 5 日均線時獲利出場（主升段結束訊號）\n"
            "◆ 加速出場：MACD 柱狀體由放大轉縮小，動能衰退時先行了結"
        )

    # ---------- IV 異常警示 ----------

    def get_iv_warning_note(self) -> str:
        """回傳 IV 警示區段說明文字"""
        return (
            "【IV/HV 異常警示說明】\n"
            "IV/HV 比率 > 1.5 的標的，可能遭遇造市商惡意拉高隱含波動率（IV），\n"
            "導致即使現股上漲，權證因 IV 被壓回而損失慘重。\n"
            "強烈建議迴避此類標的，或待 IV 回落正常水位後再考慮進場。\n"
            "◆ 正常區間：IV/HV 0.70 ~ 1.30\n"
            "◆ 注意區間：IV/HV 1.30 ~ 1.50\n"
            "◆ 高風險區間：IV/HV > 1.50（建議迴避）"
        )

    def get_iv_risk_level(self, iv_hv_ratio: float) -> str:
        """
        依 IV/HV 比率回傳風險等級文字。

        Args:
            iv_hv_ratio: IV/HV 比率值

        Returns:
            "正常" / "注意" / "高風險"
        """
        if iv_hv_ratio <= 1.30:
            return "正常"
        elif iv_hv_ratio <= 1.50:
            return "注意"
        else:
            return "高風險"

    # ---------- 希臘字母 Tooltip ----------

    def get_greek_tooltip(self, greek_name: str) -> str:
        """
        回傳希臘字母指標的交易員解讀說明，供 GUI Tooltip 顯示。

        Args:
            greek_name: 欄位名稱，如 "DELTA", "GAMMA", "THETA", "VEGA", "IV_HV_ratio"

        Returns:
            說明文字字串
        """
        tooltips = {
            "DELTA": (
                "Delta (Δ) — 連動性\n"
                "現股每漲 1 元，權證漲幾元。\n"
                "建倉階段選 0.4~0.6（價平附近，連動性佳）\n"
                "加碼階段選 0.05~0.30（微價外，利用 Gamma 爆發）"
            ),
            "GAMMA": (
                "Gamma (Γ) — Delta 的加速度\n"
                "主升段最關鍵指標：當現股快速上漲時，\n"
                "Gamma 使 Delta 快速增加，權證漲幅呈幾何級數放大。\n"
                "價外→價內過程中 Gamma 效果最顯著。"
            ),
            "THETA": (
                "Theta (Θ) — 時間價值每日消耗\n"
                "每過一天，權證損失的時間價值（元）。\n"
                "Theta 為負值，數值越大代表消耗越快。\n"
                "建倉階段選長天期以降低 Theta 損耗。"
            ),
            "VEGA": (
                "Vega (ν) — IV 敏感度\n"
                "隱含波動率（IV）每變化 1%，權證價格的變動量。\n"
                "IV 被造市商拉高時，Vega 大的權證損失更嚴重。"
            ),
            "IV_HV_ratio": (
                "IV/HV 比 — 造市品質指標\n"
                "隱含波動（IV）/ 歷史波動（HV）\n"
                "● 0.70~1.30：正常，可安心交易\n"
                "● 1.30~1.50：注意，造市商可能微幅調高\n"
                "● > 1.50：高風險，強烈建議迴避"
            ),
            "有效槓桿": (
                "有效槓桿（實質槓桿）\n"
                "現股漲 1% 時，權證約漲幾 %。\n"
                "主升段選同標的中有效槓桿前 30% 的標的，\n"
                "配合高 Gamma 效果最大化獲利。"
            ),
            "剩餘期間(日)": (
                "剩餘天數\n"
                "建倉階段選 > 90 天（減少 Theta 消耗）\n"
                "加碼階段選 60~120 天（承受 Theta 換高槓桿）"
            ),
        }
        return tooltips.get(greek_name, greek_name)

    # ---------- 報告標題與封面文字 ----------

    def get_report_title(self) -> str:
        """回傳 PDF 報告書主標題"""
        return "台股權證兩階段選股分析報告"

    def get_report_subtitle(self, stock_name: str, report_date: str) -> str:
        """回傳 PDF 報告書副標題"""
        stock_part = f"標的：{stock_name}" if stock_name else "全市場篩選"
        return f"{stock_part}　　分析日期：{report_date}"

    def get_phase1_title(self) -> str:
        """回傳階段一章節標題"""
        return "【階段一】突破起漲 — 安全建倉"

    def get_phase2_title(self) -> str:
        """回傳階段二章節標題"""
        return "【階段二】主升段飆漲 — 極致動能加碼"

    def get_iv_warning_title(self) -> str:
        """回傳 IV 警示章節標題"""
        return "【警示】IV/HV 異常標的（建議迴避）"
