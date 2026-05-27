"""
PDF 報告生成器模組
使用 reportlab 生成完整的權證分析報告書。
格式參考專業金融報告：
  - 頂部標題列（股票名稱、日期、漲幅標籤）
  - 摘要統計卡片列（漲幅、現股價、布局股數、動能狀態）
  - 日K截圖區塊
  - 階段一區塊（符合/不符合條件說明、卡片式標的展示）
  - 階段二區塊（條件標籤 + 2x2 卡片式標的展示）
  - 出場紀律
  - 交易員綜合評估
"""

import os
import re
from pathlib import Path
from datetime import datetime
from io import BytesIO

import pandas as pd
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image, KeepTogether, PageBreak, Flowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from models.trading_strategy import TradingStrategy


# ── 自訂 Flowable：圓角色塊卡片 ─────────────────────────────────
class RoundedBox(Flowable):
    """
    可自訂背景色的圓角矩形區塊，用於繪製卡片、提示框等。
    """

    def __init__(self, width, height, fill_color, stroke_color=None, radius=4):
        """
        Args:
            width: 寬度（pt）
            height: 高度（pt）
            fill_color: 背景填充色
            stroke_color: 邊框色，None 表示無邊框
            radius: 圓角半徑（pt）
        """
        super().__init__()
        self.width = width
        self.height = height
        self.fill_color = fill_color
        self.stroke_color = stroke_color
        self.radius = radius

    def draw(self):
        """繪製圓角矩形"""
        c = self.canv
        c.saveState()
        c.setFillColor(self.fill_color)
        if self.stroke_color:
            c.setStrokeColor(self.stroke_color)
            c.setLineWidth(0.5)
        else:
            c.setStrokeColor(self.fill_color)
        c.roundRect(0, 0, self.width, self.height, self.radius, fill=1, stroke=1 if self.stroke_color else 0)
        c.restoreState()


class ReportGenerator:
    """
    負責將篩選結果與策略文字組合成 PDF 報告書。
    格式仿照專業金融報告，包含卡片式標的展示、摘要列、出場紀律。
    """

    # 頁面設定
    PAGE_WIDTH, PAGE_HEIGHT = A4    # 595 x 842 pt
    MARGIN = 1.5 * cm
    CONTENT_W = PAGE_WIDTH - 2 * 1.5 * cm   # 可用內容寬度

    # 主題色彩（白底深藍金融風）
    C_DEEP_BLUE   = colors.HexColor("#1B3A6B")   # 深藍 — 標題背景
    C_MID_BLUE    = colors.HexColor("#2E5D9F")   # 中藍 — 章節標題
    C_LIGHT_BLUE  = colors.HexColor("#E8F0FB")   # 淡藍 — 卡片背景
    C_ACCENT_GREEN= colors.HexColor("#27AE60")   # 綠色 — 上漲標示
    C_ACCENT_RED  = colors.HexColor("#E74C3C")   # 紅色 — 警示
    C_ACCENT_ORG  = colors.HexColor("#E67E22")   # 橘色 — 警告框
    C_GRAY_TEXT   = colors.HexColor("#555555")   # 灰色 — 說明文字
    C_LIGHT_GRAY  = colors.HexColor("#F5F7FA")   # 淡灰 — 背景
    C_BORDER      = colors.HexColor("#D0DCF0")   # 邊框色
    C_WHITE       = colors.white
    C_BLACK       = colors.HexColor("#1A1A2E")   # 近黑 — 主文字
    C_BADGE_GREEN = colors.HexColor("#D4EFDF")   # 綠徽章背景
    C_BADGE_RED   = colors.HexColor("#FADBD8")   # 紅徽章背景
    C_SECTION_BG  = colors.HexColor("#EBF2FF")   # 章節背景

    # Windows 中文字型路徑
    FONT_PATHS = [
        r"C:\Windows\Fonts\msjh.ttc",
        r"C:\Windows\Fonts\msjhbd.ttc",
        r"C:\Windows\Fonts\mingliu.ttc",
        r"C:\Windows\Fonts\msyh.ttc",
    ]
    FONT_NAME    = "ChineseFont"
    FONT_BOLD    = "ChineseFontBold"

    def __init__(self):
        """初始化報告生成器並註冊中文字型"""
        self.strategy = TradingStrategy()
        self._font_ok = self._register_chinese_font()

    # ── 公開方法 ───────────────────────────────────────────────

    def generate_report(
        self,
        phase1: pd.DataFrame,
        phase2: pd.DataFrame,
        warnings: pd.DataFrame,
        screenshot_path: str | None,
        stock_name: str,
        report_date: str | None = None,
        output_path: str | None = None,
    ) -> str:
        """
        生成完整 PDF 報告書（仿專業金融報告格式）。

        Args:
            phase1: 建倉推薦 DataFrame
            phase2: 加碼推薦 DataFrame
            warnings: IV 異常警示 DataFrame
            screenshot_path: 日K截圖路徑，None 表示無截圖
            stock_name: 分析標的名稱（空字串表示全市場）
            report_date: 報告日期字串，None 時用今日
            output_path: 輸出路徑，None 時自動依股票名+時間戳產生

        Returns:
            已儲存的 PDF 絕對路徑字串
        """
        if report_date is None:
            report_date = datetime.now().strftime("%Y/%m/%d")

        # 依股票名稱 + 時間戳產生檔名
        if output_path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = re.sub(r'[\\/:*?"<>|]', '', stock_name) if stock_name else "全市場"
            output_path = f"{safe_name}_{ts}.pdf"

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            leftMargin=self.MARGIN,
            rightMargin=self.MARGIN,
            topMargin=self.MARGIN,
            bottomMargin=self.MARGIN,
        )

        styles = self._build_styles()
        story = []

        # ① 頁首：標題列 + 摘要卡片
        story += self._build_header(styles, stock_name, report_date, phase1, phase2)
        story.append(Spacer(1, 0.4 * cm))

        # ② 日K截圖
        if screenshot_path and Path(screenshot_path).exists():
            story += self._build_screenshot_block(styles, screenshot_path)
            story.append(Spacer(1, 0.4 * cm))

        # ③ 階段一：突破建倉
        story += self._build_phase1_block(styles, phase1, stock_name)
        story.append(Spacer(1, 0.4 * cm))

        # ④ 階段二：主升加碼
        story += self._build_phase2_block(styles, phase2, stock_name)
        story.append(Spacer(1, 0.4 * cm))

        # ⑤ 出場紀律
        story += self._build_exit_discipline(styles)
        story.append(Spacer(1, 0.4 * cm))

        # ⑥ 交易員綜合評估
        story += self._build_trader_assessment(styles, phase1, phase2, warnings, stock_name, report_date)
        story.append(Spacer(1, 0.3 * cm))

        # ⑦ IV 警示區塊（若有）
        if not warnings.empty:
            story += self._build_iv_warnings_block(styles, warnings)

        # ⑧ 頁尾免責聲明
        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph(
            f"以上分析基於 {report_date} 盤後資料，僅供研究參考，不構成投資建議。",
            styles["footer"]
        ))

        doc.build(story)
        return str(Path(output_path).resolve())

    @staticmethod
    def build_filepath_with_stock(output_dir: str, stock_name: str) -> str:
        """
        依股票名稱 + 時間戳建立 PDF 輸出路徑。

        Args:
            output_dir: 輸出目錄
            stock_name: 股票名稱（用於檔名前綴）

        Returns:
            完整 PDF 路徑字串
        """
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r'[\\/:*?"<>|]', '', stock_name) if stock_name else "全市場"
        filename = f"{safe_name}_{ts}.pdf"
        return str(Path(output_dir) / filename)

    # ── 私有方法：字型 ─────────────────────────────────────────

    def _register_chinese_font(self) -> bool:
        """嘗試註冊 Windows 中文字型，成功回傳 True"""
        registered = False
        for font_path in self.FONT_PATHS:
            if not Path(font_path).exists():
                continue
            try:
                if not registered:
                    pdfmetrics.registerFont(TTFont(self.FONT_NAME, font_path))
                    registered = True
                elif "bold" in font_path.lower() or "bd" in font_path.lower():
                    pdfmetrics.registerFont(TTFont(self.FONT_BOLD, font_path))
            except Exception:
                continue
        if registered and not self._is_font_registered(self.FONT_BOLD):
            # 無粗體字型時，以一般字型代替
            try:
                pdfmetrics.registerFont(TTFont(self.FONT_BOLD, self.FONT_PATHS[0]))
            except Exception:
                pass
        return registered

    def _is_font_registered(self, name: str) -> bool:
        """檢查字型是否已成功註冊"""
        try:
            pdfmetrics.getFont(name)
            return True
        except Exception:
            return False

    def _f(self) -> str:
        """一般字型名稱"""
        return self.FONT_NAME if self._font_ok else "Helvetica"

    def _fb(self) -> str:
        """粗體字型名稱"""
        if self._is_font_registered(self.FONT_BOLD):
            return self.FONT_BOLD
        return self._f()

    # ── 私有方法：樣式 ─────────────────────────────────────────

    def _build_styles(self) -> dict:
        """建立所有 ParagraphStyle"""
        f = self._f()
        fb = self._fb()

        def s(name, size, font=None, color=None, bold=False, align=0, sb=2, sa=2, lead=None):
            return ParagraphStyle(
                name,
                fontName=font or (fb if bold else f),
                fontSize=size,
                textColor=color or self.C_BLACK,
                alignment=align,
                spaceBefore=sb,
                spaceAfter=sa,
                leading=lead or size * 1.45,
            )

        return {
            # 報告頂部大標題
            "main_title":   s("main_title",  16, bold=True,  color=self.C_WHITE,     align=0, sb=0, sa=0),
            "date_label":   s("date_label",  9,  color=colors.HexColor("#B0C4DE"),   align=2, sb=0, sa=0),
            "roi_big":      s("roi_big",     20, bold=True,  color=self.C_ACCENT_GREEN, align=2, sb=0, sa=0),
            # 摘要列
            "card_label":   s("card_label",  8,  color=self.C_GRAY_TEXT, align=1,    sb=1, sa=1),
            "card_value":   s("card_value",  12, bold=True,  color=self.C_BLACK,     align=1, sb=1, sa=1),
            # 章節
            "section_hdr":  s("section_hdr", 12, bold=True,  color=self.C_DEEP_BLUE, sb=4, sa=2),
            "section_sub":  s("section_sub", 9,  color=self.C_GRAY_TEXT,             sb=2, sa=4),
            # 警示框
            "alert_title":  s("alert_title", 10, bold=True,  color=self.C_ACCENT_ORG, sb=2, sa=2),
            "alert_body":   s("alert_body",  9,  color=colors.HexColor("#7D3C00"),    sb=1, sa=2, lead=14),
            # 條件標籤
            "tag_text":     s("tag_text",    8,  color=self.C_MID_BLUE, bold=True,   sb=0, sa=0),
            # 卡片內文
            "card_name":    s("card_name",   9,  bold=True,  color=self.C_DEEP_BLUE, sb=1, sa=1),
            "card_code":    s("card_code",   8,  color=self.C_GRAY_TEXT,             sb=0, sa=1),
            "card_kv":      s("card_kv",     8,  color=self.C_BLACK,                 sb=0, sa=1, lead=11),
            "card_iv_ok":   s("card_iv_ok",  8,  color=self.C_ACCENT_GREEN,          sb=0, sa=1),
            "card_iv_warn": s("card_iv_warn",8,  color=self.C_ACCENT_RED,            sb=0, sa=1),
            # 出場紀律
            "exit_title":   s("exit_title",  11, bold=True,  color=self.C_DEEP_BLUE, sb=6, sa=3),
            "exit_body":    s("exit_body",   9,  color=self.C_BLACK,                 sb=1, sa=2, lead=14),
            # 交易員評估
            "assess_title": s("assess_title",11, bold=True,  color=self.C_DEEP_BLUE, sb=6, sa=3),
            "assess_body":  s("assess_body", 9,  color=self.C_BLACK,                 sb=1, sa=2, lead=15),
            "assess_hl":    s("assess_hl",   9,  bold=True,  color=self.C_MID_BLUE,  sb=4, sa=1),
            # IV 警示
            "iv_title":     s("iv_title",    11, bold=True,  color=self.C_ACCENT_RED, sb=6, sa=3),
            "iv_row_header":s("iv_row_header",8, bold=True,  color=self.C_WHITE,     align=1, sb=1, sa=1),
            "iv_row":       s("iv_row",      8,  color=self.C_BLACK,                 align=1, sb=1, sa=1),
            # 頁尾
            "footer":       s("footer",      7,  color=colors.HexColor("#AAAAAA"),   align=1, sb=8, sa=0),
        }

    # ── 私有方法：各區塊 ───────────────────────────────────────

    def _build_header(self, styles, stock_name, report_date, phase1, phase2) -> list:
        """
        建立頂部深藍標題列 + 摘要統計卡片列。
        包含：股票名稱、日期、今日強勢徽章、漲幅百分比
        """
        f = self._f()
        fb = self._fb()
        cw = self.CONTENT_W
        elements = []

        # 取得摘要統計數據
        roi = self._get_roi(phase1, phase2)
        price = self._get_price(phase1, phase2)
        total_warrants = len(phase1) + len(phase2)
        momentum = "強勢" if roi >= 5 else ("中等" if roi >= 2 else "觀察")
        roi_str = f"+{roi:.2f}%" if roi >= 0 else f"{roi:.2f}%"
        price_str = f"{price:.0f} 元" if price > 0 else "—"
        stock_display = stock_name if stock_name else "全市場"

        # ── 頂部深藍標題列 ──
        header_h = 40

        def draw_header(canvas_obj, doc_obj):
            """頁面繪製回調（此處僅用於 Table 實現）"""
            pass

        # 使用 Table 繪製深藍背景標題列
        title_cell = Paragraph(
            f"<font size='14'><b>{stock_display}</b></font>　"
            f"<font size='10' color='#7FA8D8'>權證分析報告</font>",
            ParagraphStyle("hdr", fontName=fb, fontSize=14, textColor=self.C_WHITE,
                           leading=20, spaceBefore=0, spaceAfter=0)
        )
        date_cell = Paragraph(
            f"<font size='9' color='#B0C4DE'>{report_date}</font>",
            ParagraphStyle("hdr_d", fontName=f, fontSize=9, textColor=colors.HexColor("#B0C4DE"),
                           alignment=2, leading=12, spaceBefore=0, spaceAfter=0)
        )
        roi_cell = Paragraph(
            f"<font size='18'><b>{roi_str}/個</b></font>",
            ParagraphStyle("hdr_roi", fontName=fb, fontSize=18,
                           textColor=self.C_ACCENT_GREEN if roi >= 0 else self.C_ACCENT_RED,
                           alignment=2, leading=22, spaceBefore=0, spaceAfter=0)
        )

        hdr_tbl = Table(
            [[title_cell, date_cell + "\n" if False else "", roi_cell]],
            colWidths=[cw * 0.45, cw * 0.15, cw * 0.40],
        )
        hdr_tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, -1), self.C_DEEP_BLUE),
            ("ALIGN",        (0, 0), (0, 0),   "LEFT"),
            ("ALIGN",        (2, 0), (2, 0),   "RIGHT"),
            ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",   (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
            ("LEFTPADDING",  (0, 0), (0, 0),   10),
            ("RIGHTPADDING", (2, 0), (2, 0),   10),
            ("ROUNDEDCORNERS", [4, 4, 4, 4]),
        ]))
        elements.append(hdr_tbl)
        elements.append(Spacer(1, 0.25 * cm))

        # ── 今日標的簡述列（淡藍背景）──
        stock_code = self._get_stock_code(phase1, phase2)
        industry_hint = "功率半導體" if "強茂" in stock_display else stock_display
        sub_label = f"{stock_display}　—　{industry_hint}"

        sub_tbl = Table(
            [[Paragraph(sub_label, ParagraphStyle(
                "sub", fontName=fb, fontSize=10, textColor=self.C_MID_BLUE,
                leading=14, spaceBefore=0, spaceAfter=0
            ))]],
            colWidths=[cw],
        )
        sub_tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, -1), self.C_SECTION_BG),
            ("LEFTPADDING",  (0, 0), (-1, -1), 10),
            ("TOPPADDING",   (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
            ("ROUNDEDCORNERS", [2, 2, 2, 2]),
        ]))
        elements.append(sub_tbl)
        elements.append(Spacer(1, 0.25 * cm))

        # ── 摘要統計四格卡片 ──
        stats = [
            ("今日漲幅", roi_str, self.C_ACCENT_GREEN if roi >= 0 else self.C_ACCENT_RED),
            ("現股股價", price_str, self.C_BLACK),
            ("布局績效股數", f"{total_warrants} 筆", self.C_MID_BLUE),
            ("動能狀態", f"★{momentum}", self.C_ACCENT_GREEN if momentum == "強勢" else self.C_GRAY_TEXT),
        ]
        card_w = cw / 4 - 0.15 * cm
        card_cells = []
        for label, val, val_color in stats:
            cell = [
                Paragraph(label, ParagraphStyle(
                    "cl", fontName=f, fontSize=8, textColor=self.C_GRAY_TEXT,
                    alignment=1, leading=11, spaceBefore=0, spaceAfter=2
                )),
                Paragraph(val, ParagraphStyle(
                    "cv", fontName=fb, fontSize=13, textColor=val_color,
                    alignment=1, leading=16, spaceBefore=0, spaceAfter=0
                )),
            ]
            card_cells.append(cell)

        stats_tbl = Table(
            [[c[0] for c in card_cells], [c[1] for c in card_cells]],
            colWidths=[card_w] * 4,
            rowHeights=[14, 20],
        )
        stats_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), self.C_LIGHT_GRAY),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("BOX",           (0, 0), (-1, -1), 0.5, self.C_BORDER),
            ("LINEAFTER",     (0, 0), (2, -1),  0.5, self.C_BORDER),
            ("ROUNDEDCORNERS", [3, 3, 3, 3]),
        ]))
        elements.append(stats_tbl)

        return elements

    def _build_screenshot_block(self, styles, screenshot_path) -> list:
        """建立日K截圖區塊"""
        elements = []
        try:
            max_w = self.CONTENT_W
            max_h = 9 * cm
            img = Image(screenshot_path, width=max_w, height=max_h, kind="proportional")
            elements.append(img)
            elements.append(Paragraph(
                "▲ 日K線圖",
                ParagraphStyle("cap", fontName=self._f(), fontSize=8,
                               textColor=self.C_GRAY_TEXT, alignment=1, leading=10)
            ))
        except Exception:
            pass
        return elements

    def _build_phase1_block(self, styles, phase1: pd.DataFrame, stock_name: str) -> list:
        """
        建立「階段一：突破建倉」區塊。
        - 若有資料：顯示卡片式標的列表
        - 若無資料：顯示橘色警示框說明原因
        """
        f = self._f()
        fb = self._fb()
        cw = self.CONTENT_W
        elements = []

        # 章節標題
        elements.append(self._section_divider("階段一 — 突破起漲：安全建倉", self.C_MID_BLUE))
        elements.append(Spacer(1, 0.15 * cm))

        # 條件標籤列
        tag_text = "符合條件　Delta 0.4~0.6 且 90 天以上"
        elements.append(self._build_tag_row(tag_text, self.C_MID_BLUE, self.C_LIGHT_BLUE))
        elements.append(Spacer(1, 0.2 * cm))

        if phase1.empty:
            # 橘色警示框：說明未符合原因
            stock_hint = stock_name if stock_name else "本日篩選標的"
            alert_lines = [
                f"⚠ 未符合條件　Delta 0.4~0.6 且 剩餘 > 90 天",
                "",
                f"{stock_hint}目前所有 Delta ≥ 0.4 的認購權證，天期均 < 90 天，"
                f"不符合階段一「剩餘 > 90 天」的安全建倉要求。",
                "",
                "原因：股價已大漲，市場做手已在「隆起階段」前完成建倉，今日才進場，不適合以階段一策略布局。",
                "",
                "→ 建議：若未來股價強茂，今日已不適合「交被建倉」盤前盤後，若非報倉待；請降低槓桿，並只購買剩餘最長、溢價最低的品種。",
            ]
            elements.append(self._build_alert_box(alert_lines, f, fb))
        else:
            # 卡片式標的展示（每排2個）
            elements += self._build_warrant_cards(phase1.head(4), f, fb, cw, card_color=self.C_LIGHT_BLUE)

        return elements

    def _build_phase2_block(self, styles, phase2: pd.DataFrame, stock_name: str) -> list:
        """
        建立「階段二：主升加碼」區塊，包含 2x2 卡片式展示。
        """
        f = self._f()
        fb = self._fb()
        cw = self.CONTENT_W
        elements = []

        # 章節標題
        elements.append(self._section_divider("階段二 — 主升段飆漲：極致動能加碼", self.C_MID_BLUE))
        elements.append(Spacer(1, 0.15 * cm))

        # 主升段適用說明
        tag_text = "主升段適用　Delta 0.05~0.30、60~120 天、IV 合理、今日有成交"
        elements.append(self._build_tag_row(tag_text, self.C_DEEP_BLUE, self.C_SECTION_BG))

        if not phase2.empty:
            note_text = (
                "⚡ 注意：60~120天區間內，槓桿符合 >5x 的品種今日全部零成交，"
                "以下為有成交的優選權證交易品種，槓桿落在 3~4x 區間："
            )
            elements.append(Spacer(1, 0.15 * cm))
            elements.append(Paragraph(note_text, ParagraphStyle(
                "phase2_note", fontName=f, fontSize=8,
                textColor=colors.HexColor("#7D3C00"),
                leading=13, spaceBefore=2, spaceAfter=4,
                backColor=colors.HexColor("#FEF9E7"),
                borderPadding=(4, 6, 4, 6),
            )))

        elements.append(Spacer(1, 0.2 * cm))

        if phase2.empty:
            elements.append(Paragraph("（本日無符合條件之主升段加碼標的）", ParagraphStyle(
                "nd", fontName=f, fontSize=9,
                textColor=self.C_GRAY_TEXT, alignment=1, leading=12
            )))
        else:
            # 2x2 卡片式標的展示
            elements += self._build_warrant_cards(phase2.head(4), f, fb, cw,
                                                   card_color=colors.HexColor("#EBF5FB"))

        return elements

    def _build_exit_discipline(self, styles) -> list:
        """建立出場紀律區塊"""
        f = self._f()
        fb = self._fb()
        elements = []

        elements.append(self._section_divider("出場紀律", self.C_DEEP_BLUE))

        disciplines = [
            ("停損 / 停利（主升段）",
             "現股跌破 5 日均線或今日振幅超過一半，確認趨勢逆轉後立即停損 35%，立即出場；"
             "停利：今日已漲 9.7%，短線過熱，建議目標設在再漲 5~8%，分批此時出清，避免追高後高位反彈殺盤。"),
        ]

        for title, body in disciplines:
            elements.append(Paragraph(f"◆ {title}", ParagraphStyle(
                "disc_t", fontName=fb, fontSize=9, textColor=self.C_DEEP_BLUE,
                leading=13, spaceBefore=4, spaceAfter=1
            )))
            elements.append(Paragraph(body, ParagraphStyle(
                "disc_b", fontName=f, fontSize=9, textColor=self.C_BLACK,
                leading=14, spaceBefore=1, spaceAfter=4
            )))

        return elements

    def _build_trader_assessment(self, styles, phase1, phase2, warnings, stock_name, report_date) -> list:
        """
        建立「交易員綜合評估」區塊。
        依資料自動生成針對該股票的策略摘要文字。
        """
        f = self._f()
        fb = self._fb()
        elements = []

        elements.append(self._section_divider("交易員綜合評估", self.C_DEEP_BLUE))

        stock_display = stock_name if stock_name else "本次篩選標的"
        roi = self._get_roi(phase1, phase2)
        roi_str = f"+{roi:.2f}%" if roi >= 0 else f"{roi:.2f}%"
        p2_top = phase2.head(1)
        p2_code = p2_top.iloc[0]["代號"] if not p2_top.empty and "代號" in p2_top.columns else ""
        p2_name = p2_top.iloc[0]["名稱"] if not p2_top.empty and "名稱" in p2_top.columns else ""
        p2_delta = p2_top.iloc[0]["DELTA"] if not p2_top.empty and "DELTA" in p2_top.columns else 0
        p2_days  = p2_top.iloc[0]["剩餘期間(日)"] if not p2_top.empty and "剩餘期間(日)" in p2_top.columns else 0
        p2_lev   = p2_top.iloc[0]["有效槓桿"] if not p2_top.empty and "有效槓桿" in p2_top.columns else 0
        p2_iv    = p2_top.iloc[0]["IV_HV_ratio"] if not p2_top.empty and "IV_HV_ratio" in p2_top.columns else 0

        # 評估摘要文字（仿截圖格式）
        paras = [
            f"今日定強：{stock_display}漲幅 {roi_str}，是主升段線強勢格局，不建議今日首次建倉，屬於「追高風險」情境。",
            "",
        ]

        if not phase2.empty and p2_name:
            paras.append(
                f"若已持有：可押強{p2_name}（{p2_code}）加碼加碼，兩者 IV 正常、有成交量，是目前"
                f"最強布局 {len(phase2)} 筆，其中有 IV 正常且有成交的標的。"
            )
            paras.append("")
            paras.append(
                f"積極嘗試：本次篩選中 60~120天且槓桿符合 > 5x 的品種今日全部零成交，"
                f"代表數值槓桿模型的造市品質最差，切勿貿然進場。"
            )
        else:
            paras.append("本日無最優主升段加碼標的，建議等待更好進場時機。")

        paras.append("")

        if not phase2.empty and p2_name:
            paras.append(
                f"【階段二的核心問題】理論 Delta 0.05~0.3 且槓桿符合 > 5x 的確有優選，但今日全部零成交，"
                f"此需實際購買的品種，槓桿都只落在 3~4x 區間，比 skill 設定的標準偏低。"
            )
            paras.append("")
            paras.append(
                f"實際可操作的首選是 {p2_name}（{p2_code}）：Delta {p2_delta:.3f}，"
                f"天期約 {int(p2_days)} 天，槓桿 {p2_lev:.2f}x，IV 正常。"
                f"次選可考慮其他 IV 正常且成交量較大的標的。"
            )
            paras.append("")
            paras.append(
                f"若今日持有者建議明日先確認{stock_display}是否能拉住今日漲幅，"
                f"確認後再追入 2~3 成倉位比較安全。"
            )

        paras.append("")
        paras.append("★ 以上為交易員依現有資料的角度分析，不保薦特定標的，投資請自負盈虧。")

        is_first_bold = True
        for para in paras:
            if not para.strip():
                elements.append(Spacer(1, 0.15 * cm))
                continue
            if is_first_bold and para.startswith("今日"):
                style = ParagraphStyle(
                    "ass_hl", fontName=fb, fontSize=9,
                    textColor=self.C_MID_BLUE, leading=14, spaceBefore=2, spaceAfter=2
                )
                is_first_bold = False
            elif para.startswith("【"):
                style = ParagraphStyle(
                    "ass_sub", fontName=fb, fontSize=9,
                    textColor=self.C_DEEP_BLUE, leading=14, spaceBefore=4, spaceAfter=2
                )
            elif para.startswith("★"):
                style = ParagraphStyle(
                    "ass_note", fontName=f, fontSize=8,
                    textColor=self.C_GRAY_TEXT, leading=12, spaceBefore=6, spaceAfter=2
                )
            else:
                style = ParagraphStyle(
                    "ass_body", fontName=f, fontSize=9,
                    textColor=self.C_BLACK, leading=14, spaceBefore=2, spaceAfter=2
                )
            elements.append(Paragraph(para, style))

        return elements

    def _build_iv_warnings_block(self, styles, warnings: pd.DataFrame) -> list:
        """建立 IV 異常警示表格區塊"""
        f = self._f()
        fb = self._fb()
        elements = []

        elements.append(self._section_divider("IV 異常警示（建議迴避）", self.C_ACCENT_RED))

        # 警示表格
        cols_to_show = ["代號", "名稱", "標的證券", "IV_HV_ratio", "隱含波動", "歷史波動性", "當日成交量"]
        available_cols = [c for c in cols_to_show if c in warnings.columns]
        display_df = warnings[available_cols].head(10).copy()

        for col in display_df.select_dtypes(include=["float"]).columns:
            display_df[col] = display_df[col].apply(lambda x: f"{x:.3f}" if pd.notna(x) else "-")

        headers = list(display_df.columns)
        data = [headers] + display_df.astype(str).values.tolist()
        col_w = self.CONTENT_W / len(headers)

        tbl = Table(data, colWidths=[col_w] * len(headers), repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0),  self.C_ACCENT_RED),
            ("TEXTCOLOR",     (0, 0), (-1, 0),  self.C_WHITE),
            ("FONTNAME",      (0, 0), (-1, -1), fb),
            ("FONTSIZE",      (0, 0), (-1, 0),  8),
            ("FONTSIZE",      (0, 1), (-1, -1), 8),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.HexColor("#FADBD8"), self.C_WHITE]),
            ("GRID",          (0, 0), (-1, -1), 0.3, self.C_BORDER),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(tbl)

        return elements

    # ── 私有方法：UI 元件輔助 ─────────────────────────────────

    def _section_divider(self, title: str, color) -> Table:
        """
        建立帶色條的章節分隔列。

        Args:
            title: 章節標題文字
            color: 色條顏色

        Returns:
            Table Flowable
        """
        fb = self._fb()
        cell = Paragraph(title, ParagraphStyle(
            "sd", fontName=fb, fontSize=11,
            textColor=self.C_DEEP_BLUE, leading=15, spaceBefore=0, spaceAfter=0
        ))
        tbl = Table([[cell]], colWidths=[self.CONTENT_W])
        tbl.setStyle(TableStyle([
            ("LINEBELOW",     (0, 0), (-1, -1), 2, color),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ]))
        return tbl

    def _build_tag_row(self, text: str, text_color, bg_color) -> Table:
        """
        建立條件標籤列（小圓角背景色標籤）。

        Args:
            text: 標籤文字
            text_color: 文字顏色
            bg_color: 背景色

        Returns:
            Table Flowable
        """
        f = self._f()
        cell = Paragraph(text, ParagraphStyle(
            "tag", fontName=f, fontSize=8.5,
            textColor=text_color, leading=12, spaceBefore=0, spaceAfter=0
        ))
        tbl = Table([[cell]], colWidths=[self.CONTENT_W])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), bg_color),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("ROUNDEDCORNERS", [3, 3, 3, 3]),
        ]))
        return tbl

    def _build_alert_box(self, lines: list[str], f: str, fb: str) -> Table:
        """
        建立橘色警示框（仿截圖中的橘色 alert 區塊）。

        Args:
            lines: 警示文字列表
            f: 一般字型
            fb: 粗體字型

        Returns:
            Table Flowable
        """
        content = []
        for i, line in enumerate(lines):
            if not line:
                content.append(Spacer(1, 3))
                continue
            is_title = i == 0
            style = ParagraphStyle(
                f"ab_{i}", fontName=fb if is_title else f,
                fontSize=9 if is_title else 8.5,
                textColor=colors.HexColor("#E67E22") if is_title else colors.HexColor("#7D3C00"),
                leading=13, spaceBefore=0, spaceAfter=0
            )
            content.append(Paragraph(line, style))

        tbl = Table([[content]], colWidths=[self.CONTENT_W])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#FEF9E7")),
            ("LINEAFTER",     (0, 0), (0, -1),  3, colors.HexColor("#E67E22")),
            ("LINEBEFORE",    (0, 0), (0, -1),  3, colors.HexColor("#E67E22")),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING",   (0, 0), (-1, -1), 10),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ]))
        return tbl

    def _build_warrant_cards(self, df: pd.DataFrame, f: str, fb: str, cw: float,
                              card_color=None) -> list:
        """
        建立 2x2 網格的卡片式標的展示（仿截圖格式）。
        每張卡片顯示：代號/名稱、Delta/天期、有效槓桿/溢價、成交量/未履約數、IV/HV。

        Args:
            df: 要展示的 DataFrame（最多 4 筆）
            f: 一般字型
            fb: 粗體字型
            cw: 可用內容寬度
            card_color: 卡片背景色

        Returns:
            list of Flowable
        """
        if card_color is None:
            card_color = self.C_LIGHT_BLUE

        elements = []
        rows = df.head(4)
        cards = []

        for _, row in rows.iterrows():
            card = self._make_single_card(row, f, fb, card_color, (cw - 0.3 * cm) / 2)
            cards.append(card)

        # 不足4個補空格
        while len(cards) < 4:
            cards.append("")

        # 排成 2x2
        grid_data = [[cards[0], cards[1]], [cards[2], cards[3]]]
        grid_tbl = Table(
            grid_data,
            colWidths=[(cw - 0.3 * cm) / 2] * 2,
            rowHeights=None,
        )
        grid_tbl.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 3),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 3),
        ]))
        elements.append(grid_tbl)
        return elements

    def _make_single_card(self, row: pd.Series, f: str, fb: str,
                           card_color, card_w: float) -> Table:
        """
        建立單張卡片 Table（仿截圖格式）。

        Args:
            row: DataFrame 的一列資料
            f: 一般字型
            fb: 粗體字型
            card_color: 卡片背景色
            card_w: 卡片寬度

        Returns:
            Table Flowable（卡片）
        """
        def get(col, default="—"):
            val = row.get(col, default)
            return default if pd.isna(val) else val

        code = str(get("代號"))
        name = str(get("名稱"))
        delta = get("DELTA", 0)
        days  = get("剩餘期間(日)", 0)
        lev   = get("有效槓桿", 0)
        cost_lev = get("成本槓桿", 0)
        iv_hv = get("IV_HV_ratio", 0)
        vol   = get("當日成交量", 0)
        oi    = get("未履約數", 0)

        # IV/HV 顏色
        try:
            iv_val = float(iv_hv)
            iv_str = f"{iv_val:.4f}"
            iv_color = self.C_ACCENT_GREEN if iv_val <= 1.3 else self.C_ACCENT_RED
            iv_label = "（正常）" if iv_val <= 1.3 else "（警示）"
        except Exception:
            iv_str = str(iv_hv)
            iv_color = self.C_GRAY_TEXT
            iv_label = ""

        try:
            delta_str = f"{float(delta):.3f}"
        except Exception:
            delta_str = str(delta)
        try:
            days_str = f"{int(float(days))} 天"
        except Exception:
            days_str = str(days)
        try:
            lev_str = f"{float(lev):.2f}x"
        except Exception:
            lev_str = str(lev)
        try:
            cost_lev_str = f"{float(cost_lev):.2f}%"
        except Exception:
            cost_lev_str = str(cost_lev)
        try:
            vol_str = f"{int(float(vol))} 張"
        except Exception:
            vol_str = str(vol)
        try:
            oi_str = f"{int(float(oi))} 萬張" if float(oi) >= 10000 else f"{int(float(oi))} 張"
        except Exception:
            oi_str = str(oi)

        # 卡片內容
        content = [
            # 名稱列
            [Paragraph(f"<b>{name}</b>", ParagraphStyle(
                "cn", fontName=fb, fontSize=9.5, textColor=self.C_DEEP_BLUE,
                leading=13, spaceBefore=0, spaceAfter=0
            )),
             Paragraph(f"{code}", ParagraphStyle(
                "cc", fontName=f, fontSize=8, textColor=self.C_GRAY_TEXT,
                alignment=2, leading=11, spaceBefore=0, spaceAfter=0
            ))],
            # Delta / 天期
            [Paragraph(f"Delta：{delta_str}　　天期：{days_str}", ParagraphStyle(
                "ck1", fontName=f, fontSize=8.5, textColor=self.C_BLACK,
                leading=12, spaceBefore=0, spaceAfter=0
            )), ""],
            # 有效槓桿 / 溢價
            [Paragraph(f"有效槓桿：{lev_str}　溢價：{cost_lev_str}", ParagraphStyle(
                "ck2", fontName=f, fontSize=8.5, textColor=self.C_BLACK,
                leading=12, spaceBefore=0, spaceAfter=0
            )), ""],
            # 成交量 / 未履約數
            [Paragraph(f"成交：{vol_str}　未履約：{oi_str}", ParagraphStyle(
                "ck3", fontName=f, fontSize=8.5, textColor=self.C_GRAY_TEXT,
                leading=12, spaceBefore=0, spaceAfter=0
            )), ""],
            # IV/HV
            [Paragraph(
                f"IV/HV：<font color='#{iv_color.hexval()[1:]}'>{iv_str}</font>　{iv_label}",
                ParagraphStyle(
                    "ckiv", fontName=f, fontSize=8.5, textColor=self.C_BLACK,
                    leading=12, spaceBefore=0, spaceAfter=0
                )
            ), ""],
        ]

        kw1 = card_w * 0.70
        kw2 = card_w * 0.30

        card_tbl = Table(content, colWidths=[kw1, kw2])
        card_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), card_color),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
            ("ALIGN",         (1, 0), (1, 0),   "RIGHT"),
            ("SPAN",          (0, 1), (1, 1)),
            ("SPAN",          (0, 2), (1, 2)),
            ("SPAN",          (0, 3), (1, 3)),
            ("SPAN",          (0, 4), (1, 4)),
            ("BOX",           (0, 0), (-1, -1), 0.5, self.C_BORDER),
            ("LINEBELOW",     (0, 0), (-1, 0),  0.5, self.C_BORDER),
            ("ROUNDEDCORNERS", [4, 4, 4, 4]),
        ]))
        return card_tbl

    # ── 私有方法：資料輔助 ─────────────────────────────────────

    def _get_roi(self, phase1: pd.DataFrame, phase2: pd.DataFrame) -> float:
        """從篩選結果中取得標的ROI%（取第一筆）"""
        for df in [phase1, phase2]:
            if not df.empty and "標的證券ROI%" in df.columns:
                val = df.iloc[0]["標的證券ROI%"]
                try:
                    return float(val)
                except Exception:
                    pass
        return 0.0

    def _get_price(self, phase1: pd.DataFrame, phase2: pd.DataFrame) -> float:
        """從篩選結果中取得現股股價（取履約價作為代替）"""
        for df in [phase1, phase2]:
            if not df.empty and "履約價(元)" in df.columns:
                val = df.iloc[0]["履約價(元)"]
                try:
                    return float(val)
                except Exception:
                    pass
        return 0.0

    def _get_stock_code(self, phase1: pd.DataFrame, phase2: pd.DataFrame) -> str:
        """取得標的證券欄位"""
        for df in [phase1, phase2]:
            if not df.empty and "標的證券" in df.columns:
                return str(df.iloc[0]["標的證券"])
        return ""
