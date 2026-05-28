"""
應用控制器模組
負責串接 Model 層與 View 層，協調資料載入、篩選、搜尋、匯出等流程。
"""

import os
import tempfile
from pathlib import Path
from datetime import datetime

import pandas as pd
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import QObject, pyqtSignal

from models.data_loader import DataLoader
from models.warrant_filter import WarrantFilter
from models.data_exporter import DataExporter
from models.report_generator import ReportGenerator
from models.trading_strategy import TradingStrategy
from utils.config_manager import ConfigManager


class AppController(QObject):
    """
    MVC 的 Controller：串接所有 Model 元件與 View 層事件。
    透過 Qt Signal 通知 View 更新 UI，保持 View 與 Model 解耦。
    """

    # Qt 信號：通知 View 更新
    data_loaded       = pyqtSignal(str, int)       # (日期字串, 總筆數)
    phase1_updated    = pyqtSignal(object)          # phase1 DataFrame
    phase2_updated    = pyqtSignal(object)          # phase2 DataFrame
    warnings_updated  = pyqtSignal(object)          # warnings DataFrame
    stocks_list_ready = pyqtSignal(list)            # 股票名稱清單（自動補全）
    status_message    = pyqtSignal(str)             # 狀態列訊息
    error_occurred    = pyqtSignal(str)             # 錯誤訊息
    export_done       = pyqtSignal(str)             # 匯出完成的檔案路徑
    pdf_preview_ready = pyqtSignal(str)             # 傳遞預覽 PDF 路徑
    pdf_v2_preview_ready = pyqtSignal(str)          # V2 PDF 路徑
    v2_class_a_updated= pyqtSignal(object)          # V2 A級 DataFrame
    v2_class_b_updated= pyqtSignal(object)          # V2 B級 DataFrame

    def __init__(self, config: ConfigManager, parent=None):
        """
        Args:
            config: 已初始化的 ConfigManager 實例
            parent: Qt 父物件（可為 None）
        """
        super().__init__(parent)
        self._config   = config
        self._loader   = DataLoader()
        self._filter   = WarrantFilter()
        self._exporter = DataExporter()
        self._report   = ReportGenerator()
        self._strategy = TradingStrategy()

        # 內部狀態
        self._raw_df:      pd.DataFrame | None = None  # 全量預處理後資料
        self._filtered_df: pd.DataFrame | None = None  # 股票搜尋後資料
        self._phase1:      pd.DataFrame = pd.DataFrame()
        self._phase2:      pd.DataFrame = pd.DataFrame()
        self._warnings:    pd.DataFrame = pd.DataFrame()
        self._v2_class_a:  pd.DataFrame = pd.DataFrame()       # V2 A級
        self._v2_class_b:  pd.DataFrame = pd.DataFrame()       # V2 B級
        self._screenshot_path: str | None = None       # 日K截圖暫存路徑
        self._current_stock_query: str = ""            # 目前搜尋關鍵字

    # ── 公開方法 ───────────────────────────────────────────────

    def load_and_analyze(self, file_path: str | None = None) -> None:
        """
        載入 Excel 資料並執行完整分析流程。
        完成後透過信號通知各 View 元件更新。

        Args:
            file_path: Excel 路徑，None 時從設定檔讀取
        """
        path = file_path or self._config.get_excel_path()
        try:
            self.status_message.emit(f"讀取資料中：{Path(path).name} ...")
            df_raw = self._loader.load_excel(path)
            self._raw_df = self._loader.preprocess(df_raw)

            # 更新 Excel 路徑設定
            if file_path:
                self._config.set_excel_path(file_path)

            # 通知 View：資料載入完成
            date_str = (
                self._loader.latest_date.strftime("%Y/%m/%d")
                if self._loader.latest_date else "未知"
            )
            self.data_loaded.emit(date_str, len(self._raw_df))

            # 發布股票清單供搜尋補全
            stocks = self._filter.get_unique_stocks(self._raw_df)
            self.stocks_list_ready.emit(stocks)

            # 套用預設股票搜尋（僅首次載入時，若 _current_stock_query 尚未設定）
            if not self._current_stock_query:
                default_q = self._config.get_default_stock_query()
                if default_q:
                    self._current_stock_query = default_q

            # 執行篩選
            self._run_filter()

        except FileNotFoundError as e:
            self.error_occurred.emit(f"找不到檔案：{e}")
        except ValueError as e:
            self.error_occurred.emit(f"資料格式錯誤：{e}")
        except Exception as e:
            self.error_occurred.emit(f"載入失敗：{e}")

    def search_stock(self, query: str) -> None:
        """
        依股票名稱關鍵字重新篩選資料，並自動開啟 Yahoo 股市技術分析網頁。

        Args:
            query: 搜尋關鍵字，空字串表示全部
        """
        if self._raw_df is None:
            return
        self._current_stock_query = query.strip()

        # 開啟 Yahoo 股市技術分析
        if self._current_stock_query and not self._raw_df.empty:
            q = self._current_stock_query
            mask = self._raw_df["標的證券"].str.contains(q, na=False, case=False)
            matched = self._raw_df[mask]
            if not matched.empty:
                import re, webbrowser
                first_stock = matched["標的證券"].iloc[0]
                m = re.search(r'^(\d+)', str(first_stock).strip())
                if m:
                    stock_code = m.group(1)
                    url = f"https://tw.stock.yahoo.com/quote/{stock_code}.TW/technical-analysis"
                    try:
                        webbrowser.open(url)
                    except Exception as e:
                        print(f"無法開啟瀏覽器: {e}")

        self._run_filter()

    def set_default_stock_query(self, query: str) -> None:
        """
        更新預設股票並儲存到設定檔。
        下次啟動 APP 時將自動以此股票代號進行搜尋。

        Args:
            query: 股票代號或名稱字串
        """
        self._config.set_default_stock_query(query)

    def get_default_stock_query(self) -> str:
        """回傳目前儲存的預設股票代號"""
        return self._config.get_default_stock_query()

    def set_screenshot(self, image: QImage) -> None:
        """
        儲存日K截圖到暫存檔，供 PDF 報告使用。

        Args:
            image: 從剪貼簿或檔案取得的 QImage
        """
        if image.isNull():
            return
        try:
            # 儲存為暫存 PNG 檔
            tmp = tempfile.NamedTemporaryFile(
                suffix=".png", delete=False, prefix="kline_"
            )
            tmp.close()
            pixmap = QPixmap.fromImage(image)
            pixmap.save(tmp.name, "PNG")
            self._screenshot_path = tmp.name
            self._generate_preview_pdf()
        except Exception as e:
            self.error_occurred.emit(f"截圖儲存失敗：{e}")

    def clear_screenshot(self) -> None:
        """清除日K截圖暫存"""
        if self._screenshot_path and Path(self._screenshot_path).exists():
            try:
                os.remove(self._screenshot_path)
            except OSError:
                pass
        self._screenshot_path = None
        self._generate_preview_pdf()

    def set_screenshot_from_file(self, file_path: str) -> None:
        """
        從指定檔案路徑載入截圖。

        Args:
            file_path: 圖片檔案路徑（PNG/JPG/BMP）
        """
        self._screenshot_path = file_path
        self._generate_preview_pdf()

    def export_csv(self, output_dir: str | None = None) -> None:
        """匯出三個篩選結果為個別 CSV 檔案"""
        if self._phase1.empty and self._phase2.empty:
            self.error_occurred.emit("尚無篩選資料，請先載入 Excel。")
            return
        out = output_dir or self._config.get_output_dir()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            paths = []
            for name, df in [
                ("階段一_建倉", self._phase1),
                ("階段二_加碼", self._phase2),
                ("IV_警示",    self._warnings),
            ]:
                fp = str(Path(out) / f"warrant_{name}_{ts}.csv")
                self._exporter.export_csv(df, fp)
                paths.append(fp)
            self.export_done.emit(paths[0])
            self.status_message.emit(f"CSV 已匯出至：{out}")
        except Exception as e:
            self.error_occurred.emit(f"CSV 匯出失敗：{e}")

    def export_excel(self, output_dir: str | None = None) -> None:
        """匯出三個篩選結果為多分頁 Excel 檔案"""
        if self._phase1.empty and self._phase2.empty:
            self.error_occurred.emit("尚無篩選資料，請先載入 Excel。")
            return
        out = output_dir or self._config.get_output_dir()
        fp = DataExporter.build_filepath(out, "warrant_result", "xlsx")
        try:
            self._exporter.export_excel(
                {
                    "階段一_突破建倉": self._phase1,
                    "階段二_主升加碼": self._phase2,
                    "IV_異常警示":    self._warnings,
                },
                fp,
            )
            self.export_done.emit(fp)
            self.status_message.emit(f"Excel 已匯出：{Path(fp).name}")
        except Exception as e:
            self.error_occurred.emit(f"Excel 匯出失敗：{e}")

    def export_pdf(self, stock_name: str = "", output_dir: str | None = None) -> None:
        """
        生成完整 PDF 報告書。

        Args:
            stock_name: 報告封面顯示的標的名稱
            output_dir: 輸出目錄，None 時使用設定值
        """
        if self._phase1.empty and self._phase2.empty:
            self.error_occurred.emit("尚無篩選資料，請先載入 Excel。")
            return
        out = output_dir or self._config.get_output_dir()
        fp = DataExporter.build_filepath(out, "warrant_report", "pdf")
        try:
            self.status_message.emit("PDF 報告生成中...")
            saved_path = self._report.generate_report(
                phase1=self._phase1,
                phase2=self._phase2,
                warnings=self._warnings,
                screenshot_path=self._screenshot_path,
                stock_name=stock_name,
                output_path=fp,
            )
            self.export_done.emit(saved_path)
            self.status_message.emit(f"PDF 報告已儲存：{Path(saved_path).name}")
        except Exception as e:
            self.error_occurred.emit(f"PDF 生成失敗：{e}")

    def _generate_preview_pdf(self) -> None:
        """
        在背景靜默生成原版與 V2.0 預覽版 PDF 並發送訊號供 UI 更新。
        """
        if self._phase1.empty and self._phase2.empty and self._v2_class_a.empty and self._v2_class_b.empty:
            return
            
        temp_dir = Path(tempfile.gettempdir()) / "warrant_preview"
        temp_dir.mkdir(exist_ok=True)
        
        # 1. 生成原版報告書
        preview_path_v1 = str(temp_dir / "preview_report.pdf")
        try:
            saved_path_v1 = self._report.generate_report(
                phase1=self._phase1,
                phase2=self._phase2,
                warnings=self._warnings,
                screenshot_path=self._screenshot_path,
                stock_name=self._current_stock_query,
                output_path=preview_path_v1,
            )
            self.pdf_preview_ready.emit(saved_path_v1)
        except Exception as e:
            print(f"原版預覽 PDF 生成失敗: {e}")

        # 2. 生成 V2.0 報告書
        preview_path_v2 = str(temp_dir / "preview_report_v2.pdf")
        try:
            saved_path_v2 = self._report.generate_v2_report(
                class_a=self._v2_class_a,
                class_b=self._v2_class_b,
                warnings=self._warnings,
                screenshot_path=self._screenshot_path,
                stock_name=self._current_stock_query,
                output_path=preview_path_v2,
            )
            self.pdf_v2_preview_ready.emit(saved_path_v2)
        except Exception as e:
            print(f"V2.0 預覽 PDF 生成失敗: {e}")

    # ── 資料存取 ──────────────────────────────────────────────

    def get_phase1(self) -> pd.DataFrame:
        """回傳階段一篩選結果"""
        return self._phase1

    def get_phase2(self) -> pd.DataFrame:
        """回傳階段二篩選結果"""
        return self._phase2

    def get_warnings(self) -> pd.DataFrame:
        """回傳 IV 異常警示結果"""
        return self._warnings

    def get_v2_class_a(self) -> pd.DataFrame:
        """回傳 V2 A級篩選結果"""
        return self._v2_class_a

    def get_v2_class_b(self) -> pd.DataFrame:
        """回傳 V2 B級篩選結果"""
        return self._v2_class_b

    def get_strategy(self) -> TradingStrategy:
        """回傳策略物件（供 View 取得 Tooltip 等文字）"""
        return self._strategy

    def has_screenshot(self) -> bool:
        """回傳是否已載入日K截圖"""
        return bool(self._screenshot_path) and Path(self._screenshot_path).exists()

    def get_current_stock_query(self) -> str:
        """回傳目前的股票搜尋關鍵字"""
        return self._current_stock_query

    # ── 私有方法 ──────────────────────────────────────────────

    def _run_filter(self) -> None:
        """
        內部篩選流程：搜尋 → 階段一 → 階段二 → IV 警示 → 通知 View。

        模式說明：
        - 無搜尋關鍵字（全市場模式）：使用嚴格門檻篩選最優質標的
        - 有搜尋關鍵字（個股分析模式）：放寬門檻，對該股所有權證排名推薦
        """
        if self._raw_df is None:
            return

        # 依搜尋關鍵字縮減資料範圍
        base_df = self._filter.search_by_stock(
            self._raw_df, self._current_stock_query
        )
        self._filtered_df = base_df

        is_stock_mode = bool(self._current_stock_query.strip())

        if is_stock_mode:
            # ── 個股分析模式：放寬門檻，依排名推薦 ──────────────────
            self._phase1   = self._filter.filter_stock_phase1(base_df)
            self._phase2   = self._filter.filter_stock_phase2(base_df)
            self._warnings = self._filter.detect_stock_iv_warnings(base_df)
            mode_label = f"[個股模式] {self._current_stock_query}"
        else:
            # ── 全市場模式：嚴格門檻篩選 ──────────────────────────────
            p1_params  = self._config.get_phase1_params()
            p2_params  = self._config.get_phase2_params()
            iv_thresh  = self._config.get_iv_warning_threshold()
            self._phase1   = self._filter.filter_phase1(base_df, p1_params)
            self._phase2   = self._filter.filter_phase2(base_df, p2_params)
            self._warnings = self._filter.detect_iv_warnings(base_df, iv_thresh)
            mode_label = "全市場"

        # V2 策略是獨立的，不分個股或全市場模式皆可直接執行
        self._v2_class_a = self._filter.filter_v2_class_a(base_df)
        self._v2_class_b = self._filter.filter_v2_class_b(base_df)

        # 通知 View 更新
        self.phase1_updated.emit(self._phase1)
        self.phase2_updated.emit(self._phase2)
        self.warnings_updated.emit(self._warnings)
        self.v2_class_a_updated.emit(self._v2_class_a)
        self.v2_class_b_updated.emit(self._v2_class_b)
        
        # 觸發預覽更新
        self._generate_preview_pdf()

        # 更新狀態列
        self.status_message.emit(
            f"{mode_label} | 建倉推薦：{len(self._phase1)} 筆 | "
            f"加碼推薦：{len(self._phase2)} 筆 | "
            f"IV警示：{len(self._warnings)} 筆"
        )
