"""
PDF 報告生成器模組
使用 reportlab 生成完整的權證分析報告書，
封面包含日K截圖，內容涵蓋兩階段篩選結果、策略解析與出場紀律。
"""

import os
from pathlib import Path
from datetime import datetime
from io import BytesIO

import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image, KeepTogether, PageBreak,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from models.trading_strategy import TradingStrategy


class ReportGenerator:
    """
    負責將篩選結果與策略文字組合成 PDF 報告書。
    使用微軟正黑體渲染中文，封面含日K截圖。
    """

    # 頁面設定
    PAGE_WIDTH, PAGE_HEIGHT = A4  # 595 x 842 pt
    MARGIN = 2 * cm

    # 主題色彩（深藍系金融風格）
    COLOR_HEADER     = colors.HexColor("#1B3A6B")   # 深藍 — 標題列背景
    COLOR_ROW_ODD    = colors.HexColor("#F0F4FA")   # 淺藍 — 奇數列
    COLOR_ROW_EVEN   = colors.white                  # 白 — 偶數列
    COLOR_SECTION    = colors.HexColor("#2E5D9F")   # 中藍 — 章節標題
    COLOR_WARNING    = colors.HexColor("#C0392B")   # 紅 — 警示
    COLOR_TEXT       = colors.HexColor("#212121")   # 深灰 — 內文
    COLOR_ACCENT     = colors.HexColor("#E67E22")   # 橘 — 重點

    # Windows 中文字型路徑
    FONT_PATHS = [
        r"C:\Windows\Fonts\msjh.ttc",    # 微軟正黑體
        r"C:\Windows\Fonts\mingliu.ttc", # 細明體（備選）
        r"C:\Windows\Fonts\msyh.ttc",    # 微軟雅黑（簡中備選）
    ]
    FONT_NAME = "ChineseFont"

    def __init__(self):
        """初始化報告生成器並註冊中文字型"""
        self.strategy = TradingStrategy()
        self._font_registered = self._register_chinese_font()

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
        生成完整 PDF 報告書。

        Args:
            phase1: 階段一篩選結果 DataFrame
            phase2: 階段二篩選結果 DataFrame
            warnings: IV 異常警示 DataFrame
            screenshot_path: 日K截圖的暫存路徑，None 表示無截圖
            stock_name: 分析標的名稱（空字串表示全市場）
            report_date: 報告日期字串，None 時使用今日
            output_path: 輸出 PDF 路徑，None 時自動產生時間戳路徑

        Returns:
            已儲存的 PDF 絕對路徑字串
        """
        if report_date is None:
            report_date = datetime.now().strftime("%Y/%m/%d")
        if output_path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"warrant_report_{ts}.pdf"

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # 建立 PDF 文件
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

        # 封面
        story += self._build_cover(styles, stock_name, report_date, screenshot_path)
        story.append(PageBreak())

        # 階段一
        story += self._build_phase_section(
            styles,
            title=self.strategy.get_phase1_title(),
            df=phase1,
            analysis=self.strategy.get_phase1_analysis(),
            exit_text=self.strategy.get_phase1_exit_discipline(),
        )
        story.append(Spacer(1, 0.5 * cm))

        # 階段二
        story += self._build_phase_section(
            styles,
            title=self.strategy.get_phase2_title(),
            df=phase2,
            analysis=self.strategy.get_phase2_analysis(),
            exit_text=self.strategy.get_phase2_exit_discipline(),
        )
        story.append(Spacer(1, 0.5 * cm))

        # IV 警示
        story += self._build_iv_section(styles, warnings)

        doc.build(story)
        return str(Path(output_path).resolve())

    # ── 私有方法 ──────────────────────────────────────────────

    def _register_chinese_font(self) -> bool:
        """嘗試註冊 Windows 中文字型，成功回傳 True"""
        for font_path in self.FONT_PATHS:
            if Path(font_path).exists():
                try:
                    pdfmetrics.registerFont(TTFont(self.FONT_NAME, font_path))
                    return True
                except Exception:
                    continue
        return False

    def _font(self) -> str:
        """回傳可用的字型名稱"""
        return self.FONT_NAME if self._font_registered else "Helvetica"

    def _build_styles(self) -> dict:
        """建立所有 PDF 文字樣式"""
        font = self._font()
        base = getSampleStyleSheet()

        def make(name, font_size, bold=False, color=None, space_before=4, space_after=4, alignment=0):
            return ParagraphStyle(
                name,
                fontName=font,
                fontSize=font_size,
                textColor=color or self.COLOR_TEXT,
                spaceAfter=space_after,
                spaceBefore=space_before,
                alignment=alignment,
                leading=font_size * 1.4,
            )

        return {
            "title":    make("title",    22, bold=True,  color=self.COLOR_HEADER, alignment=1, space_before=20, space_after=8),
            "subtitle": make("subtitle", 13, color=colors.HexColor("#555555"), alignment=1, space_after=12),
            "section":  make("section",  13, bold=True,  color=self.COLOR_SECTION, space_before=14, space_after=6),
            "analysis": make("analysis", 10, color=self.COLOR_TEXT, space_before=4, space_after=4),
            "exit":     make("exit",     10, color=colors.HexColor("#880000"), space_before=4, space_after=8),
            "warning_note": make("warning_note", 10, color=self.COLOR_WARNING, space_before=4, space_after=8),
            "count":    make("count",    10, color=colors.HexColor("#666666"), space_after=6),
            "footer":   make("footer",    8, color=colors.HexColor("#999999"), alignment=1),
        }

    def _build_cover(self, styles, stock_name, report_date, screenshot_path) -> list:
        """建立封面頁內容"""
        font = self._font()
        elements = []

        elements.append(Spacer(1, 1.5 * cm))
        elements.append(Paragraph(self.strategy.get_report_title(), styles["title"]))
        elements.append(Paragraph(
            self.strategy.get_report_subtitle(stock_name, report_date),
            styles["subtitle"]
        ))
        elements.append(HRFlowable(
            width="100%", thickness=2,
            color=self.COLOR_HEADER, spaceAfter=14
        ))

        # 日K截圖（若存在）
        if screenshot_path and Path(screenshot_path).exists():
            try:
                max_w = self.PAGE_WIDTH - 2 * self.MARGIN
                max_h = 11 * cm
                img = Image(screenshot_path, width=max_w, height=max_h, kind="proportional")
                elements.append(img)
                elements.append(Spacer(1, 0.5 * cm))
                caption_style = ParagraphStyle(
                    "caption", fontName=font, fontSize=9,
                    textColor=colors.HexColor("#666666"), alignment=1
                )
                elements.append(Paragraph("▲ 日K線圖", caption_style))
            except Exception:
                pass  # 截圖載入失敗時忽略

        elements.append(Spacer(1, 1 * cm))
        # 報告說明框
        info_style = ParagraphStyle(
            "info", fontName=font, fontSize=10,
            textColor=colors.HexColor("#444444"),
            borderPadding=8, leading=16
        )
        elements.append(Paragraph(
            "本報告依「頂尖權證交易員」兩階段選股策略框架自動生成，<br/>"
            "包含突破起漲建倉標的（階段一）及主升段加碼標的（階段二），<br/>"
            "並附有 IV 異常警示與完整出場紀律，僅供策略參考，不構成投資建議。",
            info_style
        ))
        return elements

    def _build_phase_section(self, styles, title, df, analysis, exit_text) -> list:
        """建立單一階段的章節內容（標題 + 表格 + 解析 + 紀律）"""
        elements = []
        elements.append(HRFlowable(width="100%", thickness=1, color=self.COLOR_SECTION, spaceAfter=2))
        elements.append(Paragraph(title, styles["section"]))
        elements.append(Paragraph(f"篩選結果：{len(df)} 筆", styles["count"]))

        if not df.empty:
            elements.append(self._build_dataframe_table(df))
        else:
            no_data_style = ParagraphStyle(
                "nodata", fontName=self._font(), fontSize=10,
                textColor=colors.HexColor("#888888"), alignment=1
            )
            elements.append(Paragraph("（本日無符合條件之標的）", no_data_style))

        elements.append(Spacer(1, 0.3 * cm))

        # 交易員解析
        for line in analysis.split("\n"):
            if line.strip():
                elements.append(Paragraph(line, styles["analysis"]))

        elements.append(Spacer(1, 0.2 * cm))

        # 出場紀律
        for line in exit_text.split("\n"):
            if line.strip():
                elements.append(Paragraph(line, styles["exit"]))

        return elements

    def _build_iv_section(self, styles, df) -> list:
        """建立 IV 警示章節"""
        elements = []
        elements.append(HRFlowable(width="100%", thickness=1, color=self.COLOR_WARNING, spaceAfter=2))
        elements.append(Paragraph(self.strategy.get_iv_warning_title(), styles["section"]))
        elements.append(Paragraph(f"警示標的：{len(df)} 筆", styles["count"]))

        if not df.empty:
            elements.append(self._build_dataframe_table(df, header_color=self.COLOR_WARNING))
        else:
            no_data_style = ParagraphStyle(
                "nodata", fontName=self._font(), fontSize=10,
                textColor=colors.HexColor("#888888"), alignment=1
            )
            elements.append(Paragraph("（本日無 IV 異常警示標的）", no_data_style))

        elements.append(Spacer(1, 0.3 * cm))
        for line in self.strategy.get_iv_warning_note().split("\n"):
            if line.strip():
                elements.append(Paragraph(line, styles["warning_note"]))

        return elements

    def _build_dataframe_table(
        self, df: pd.DataFrame, max_rows: int = 25,
        header_color: colors.Color | None = None
    ):
        """將 DataFrame 轉換為 reportlab Table 物件"""
        if header_color is None:
            header_color = self.COLOR_HEADER
        font = self._font()

        # 限制欄位數與列數避免版面超出
        display_df = df.head(max_rows).copy()

        # 數值格式化
        for col in display_df.select_dtypes(include=["float"]).columns:
            display_df[col] = display_df[col].apply(
                lambda x: f"{x:.2f}" if pd.notna(x) else "-"
            )

        headers = list(display_df.columns)
        data = [headers] + display_df.astype(str).values.tolist()

        # 自動計算欄寬
        available_width = self.PAGE_WIDTH - 2 * self.MARGIN
        col_width = available_width / len(headers)
        col_widths = [col_width] * len(headers)

        tbl = Table(data, colWidths=col_widths, repeatRows=1)
        tbl.setStyle(TableStyle([
            # 標題列
            ("BACKGROUND",  (0, 0), (-1, 0),  header_color),
            ("TEXTCOLOR",   (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",    (0, 0), (-1, -1), font),
            ("FONTSIZE",    (0, 0), (-1, 0),  8),
            ("FONTSIZE",    (0, 1), (-1, -1), 8),
            ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [self.COLOR_ROW_ODD, self.COLOR_ROW_EVEN]),
            ("GRID",        (0, 0), (-1, -1), 0.3, colors.HexColor("#CCCCCC")),
            ("TOPPADDING",  (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        return tbl
