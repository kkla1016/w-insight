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
    batch_progress    = pyqtSignal(int, int, str)   # (目前處理數, 總數, 目前股票名稱)
    batch_done        = pyqtSignal(int, str)        # (成功匯出總數, 自動日期資料夾路徑)

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
        self._batch_cancelled: bool = False
        self._last_batch_skipped_stocks: list[str] = []  # 記錄上次批次被跳過的股票


    # ── 公開方法 ───────────────────────────────────────────────

    def _find_latest_excel(self, folder_path: str) -> str | None:
        """
        在指定的資料夾中尋找最新修改的 Excel 檔案。
        """
        from pathlib import Path
        folder = Path(folder_path)
        if not folder.exists() or not folder.is_dir():
            return None
        # 自動排除 Microsoft Excel 產生的以 ~$ 開頭之隱藏鎖定暫存檔
        files = [
            f for f in list(folder.glob("*.xlsx")) + list(folder.glob("*.xls"))
            if not f.name.startswith("~$")
        ]
        if not files:
            return None
        # 依最後修改時間排序，返回最新修改的檔案路徑
        try:
            latest_file = max(files, key=lambda f: f.stat().st_mtime)
            return str(latest_file)
        except Exception:
            return None

    def load_and_analyze(self, folder_path: str | None = None) -> None:
        """
        從指定的資料夾載入最新 Excel 資料並執行完整分析流程。
        完成後透過信號通知各 View 元件更新。

        Args:
            folder_path: Excel 資料夾路徑，None 時從設定檔讀取
        """
        folder = folder_path or self._config.get_excel_folder()
        latest_file = self._find_latest_excel(folder)

        # 智慧相容 Fallback：如果新資料夾下找不到 Excel 檔案，嘗試尋找原有的單一 excel_path 檔案
        if not latest_file:
            fallback_path = self._config.get_excel_path()
            if fallback_path and Path(fallback_path).exists():
                latest_file = fallback_path
                folder = str(Path(fallback_path).parent)
            else:
                self.error_occurred.emit(
                    f"在資料夾「{Path(folder).resolve()}」內找不到任何 Excel 檔案 (*.xlsx, *.xls)！\n"
                    f"請先於設定中選擇正確的 Excel 存放資料夾。"
                )
                return

        try:
            self.status_message.emit(f"尋獲最新 Excel：{Path(latest_file).name}，載入中...")
            df_raw = self._loader.load_excel(latest_file)
            self._raw_df = self._loader.preprocess(df_raw)

            # 更新持久化設定
            if folder_path:
                self._config.set_excel_folder(folder_path)
            self._config.set_excel_path(latest_file)  # 同步更新單一檔案路徑以維持相容

            # 同步在背景自動定位其他三個資料夾下的最新 Excel 檔案，並在狀態日誌中作記錄
            other_folders = {
                "三大法人每日買賣超": self._config.get_folder_institutional(),
                "日均價DATA": self._config.get_folder_daily_price(),
                "外資法人持股": self._config.get_folder_foreign_ownership(),
            }
            loaded_info = []
            for name, path in other_folders.items():
                lf = self._find_latest_excel(path)
                if lf:
                    loaded_info.append(f"{name}: {Path(lf).name}")
                else:
                    loaded_info.append(f"{name}: (未尋獲 Excel)")
            
            print(f"[智慧多目錄檢索] 目前定位：{', '.join(loaded_info)}")

            # 通知 View：資料載入完成
            date_str = (
                self._loader.latest_date.strftime("%Y/%m/%d")
                if self._loader.latest_date else "未知"
            )
            self.data_loaded.emit(date_str, len(self._raw_df))

            # 發布股票清單供搜尋補全
            stocks = self._filter.get_unique_stocks(self._raw_df)
            self.stocks_list_ready.emit(stocks)

            # 執行篩選
            self._run_filter()

        except FileNotFoundError as e:
            self.error_occurred.emit(f"找不到檔案：{e}")
        except ValueError as e:
            self.error_occurred.emit(f"資料格式錯誤：{e}")
        except Exception as e:
            self.error_occurred.emit(f"載入失敗：{e}")

    def search_stock(self, query: str, open_browser: bool = False) -> None:
        """
        依股票名稱關鍵字重新篩選資料，並選擇性自動開啟 Yahoo 股市技術分析網頁。

        Args:
            query: 搜尋關鍵字，空字串表示全部
            open_browser: 是否自動開啟瀏覽器技術分析網頁
        """
        if self._raw_df is None:
            return
        self._current_stock_query = query.strip()

        # 開啟 Yahoo 股市技術分析
        if open_browser and self._current_stock_query and not self._raw_df.empty:
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
        生成完整 PDF 報告書（同時生成原版與 V2.0 版）。

        Args:
            stock_name: 報告封面顯示的標的名稱
            output_dir: 輸出目錄，None 時使用設定值
        """
        if self._phase1.empty and self._phase2.empty and self._v2_class_a.empty and self._v2_class_b.empty:
            self.error_occurred.emit("尚無篩選資料，請先載入 Excel。")
            return
        out = output_dir or self._config.get_output_dir()
        fp_v1 = DataExporter.build_filepath(out, "warrant_report", "pdf")
        fp_v2 = DataExporter.build_filepath(out, "warrant_report_v2", "pdf")
        try:
            self.status_message.emit("PDF 報告生成中...")
            
            # 1. 生成原版報告書
            saved_path_v1 = self._report.generate_report(
                phase1=self._phase1,
                phase2=self._phase2,
                warnings=self._warnings,
                screenshot_path=self._screenshot_path,
                stock_name=stock_name,
                output_path=fp_v1,
                class_a=self._v2_class_a,
                class_b=self._v2_class_b,
            )
            
            # 2. 生成 V2.0 報告書
            saved_path_v2 = self._report.generate_v2_report(
                class_a=self._v2_class_a,
                class_b=self._v2_class_b,
                warnings=self._warnings,
                screenshot_path=self._screenshot_path,
                stock_name=stock_name,
                output_path=fp_v2,
                phase1=self._phase1,
                phase2=self._phase2,
            )
            
            self.export_done.emit(saved_path_v2)
            self.status_message.emit(f"PDF 報告已儲存：{Path(saved_path_v1).name} 與 {Path(saved_path_v2).name}")
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
                class_a=self._v2_class_a,
                class_b=self._v2_class_b,
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
                phase1=self._phase1,
                phase2=self._phase2,
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

    def cancel_batch_pdf(self) -> None:
        """使用者點選取消時，安全地中斷批次進程"""
        self._batch_cancelled = True
        self.status_message.emit("批次匯出已由使用者取消。")

    def _parse_batch_stock_list(self, file_path: str) -> list[str]:
        """
        智慧解析股票名單 Excel 檔案，模糊匹配常見列名，
        若無則自動取第一欄 (Column 0) 作為降級容錯，去重去空去空格。
        """
        import pandas as pd
        if not file_path or not os.path.exists(file_path):
            raise FileNotFoundError(f"名單 Excel 檔案不存在：{file_path}")
            
        df = pd.read_excel(file_path)
        if df.empty:
            return []
            
        target_col = None
        # 優先模糊匹配列名
        keywords = ["股票", "名稱", "代號", "證券"]
        is_matched_header = False
        for col in df.columns:
            col_str = str(col)
            if any(k in col_str for k in keywords):
                target_col = col
                is_matched_header = True
                break
                
        # 降級容錯：若無匹配列名，直接取第一欄
        if target_col is None:
            target_col = df.columns[0]
            
        # 提取資料
        raw_list = df[target_col].dropna().astype(str).tolist()
        
        # 若是降級容錯（即列名不包含關鍵字，表示可能沒有 header），將列名本身也當作第一筆資料
        if not is_matched_header:
            raw_list.insert(0, str(target_col))
        
        # 乾淨去重與去空格清理
        cleaned = []
        seen = set()
        for s in raw_list:
            s_clean = s.strip()
            if s_clean and s_clean not in seen:
                seen.add(s_clean)
                cleaned.append(s_clean)
                
        return cleaned

    def export_batch_pdf(self) -> None:
        """
        批次匯出 PDF 報告書（原版與 V2.0 版）。
        自動在配置之 output_dir 下建立以當日日期為命名的資料夾，
        智慧檢索名單資料夾中最新的 Excel 檔案並讀取名單，並迴圈各個股執行篩選與 PDF 輸出。
        """
        if self._raw_df is None:
            self.error_occurred.emit("尚無篩選資料，請先載入 Excel。")
            return
            
        batch_folder = self._config.get_batch_stock_folder()
        if not batch_folder or not os.path.exists(batch_folder):
            self.error_occurred.emit("請先在設定中指定『批次輸出股票名單資料夾』路徑。")
            return
            
        latest_excel = self._find_latest_excel(batch_folder)
        if not latest_excel:
            self.error_occurred.emit(
                f"在資料夾「{Path(batch_folder).resolve()}」內找不到任何 Excel 檔案 (*.xlsx, *.xls)！\n"
                f"請確認該資料夾中存有名單檔案。"
            )
            return
            
        # 1. 智慧解析股票名單
        try:
            stock_list = self._parse_batch_stock_list(latest_excel)
        except Exception as e:
            self.error_occurred.emit(f"讀取名單 Excel 失敗：{e}")
            return
            
        if not stock_list:
            self.error_occurred.emit("股票名單 Excel 內無有效數據。")
            return
            
        # 2. 自動在預設 output_dir 下建立當日日期子資料夾
        default_out = self._config.get_output_dir()
        today_str = datetime.now().strftime("%Y%m%d")
        target_dir = Path(default_out) / today_str
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.error_occurred.emit(f"無法建立日期資料夾「{target_dir}」：{e}")
            return
            
        # 3. 啟動批次迴圈
        self._batch_cancelled = False
        self._last_batch_skipped_stocks = []  # 開始時清空跳過清單
        total = len(stock_list)
        success_count = 0
        
        self.status_message.emit(f"開始批次處理 (共 {total} 檔)...")
        
        for idx, stock in enumerate(stock_list):
            if self._batch_cancelled:
                break
                
            # 發送進度訊號供視窗 QProgressDialog 渲染更新
            self.batch_progress.emit(idx + 1, total, stock)
            
            try:
                # 智慧模擬「個股分析模式」的過濾流程
                base_df = self._filter.search_by_stock(self._raw_df, stock)
                
                # 若完全找不到該股資料，則跳過，防止產生空白 PDF 報告
                if base_df.empty:
                    print(f"[批次匯出] 股票「{stock}」在主力 Excel 資料庫中查無資料，跳過。")
                    self._last_batch_skipped_stocks.append(stock)  # 記錄被跳過的股票
                    continue
                    
                # 執行個股篩選與排序
                p1 = self._filter.filter_stock_phase1(base_df)
                p2 = self._filter.filter_stock_phase2(base_df)
                warns = self._filter.detect_stock_iv_warnings(base_df)
                c_a = self._filter.filter_v2_class_a(base_df)
                c_b = self._filter.filter_v2_class_b(base_df)
                
                # 自動建立輸出檔名
                import re
                safe_stock = re.sub(r'[\\/:*?"<>|]', '', stock)
                fp_v1 = str(target_dir / f"warrant_report_{safe_stock}.pdf")
                fp_v2 = str(target_dir / f"warrant_report_v2_{safe_stock}.pdf")
                
                # 產生雙版本報告書
                self._report.generate_report(
                    phase1=p1,
                    phase2=p2,
                    warnings=warns,
                    screenshot_path=None,
                    stock_name=stock,
                    output_path=fp_v1,
                    class_a=c_a,
                    class_b=c_b,
                )
                
                self._report.generate_v2_report(
                    class_a=c_a,
                    class_b=c_b,
                    warnings=warns,
                    screenshot_path=None,
                    stock_name=stock,
                    output_path=fp_v2,
                    phase1=p1,
                    phase2=p2,
                )
                
                success_count += 1
                
            except Exception as e:
                # 智慧異常隔離：捕獲個股編譯錯誤，記錄日誌，絕不影響批次其它股票的生成！
                print(f"[批次匯出] 生成股票「{stock}」PDF 報告失敗：{e}")
                
        # 4. 結束處理
        if not self._batch_cancelled:
            self.batch_done.emit(success_count, str(target_dir.resolve()))
            self.status_message.emit(f"批次匯出完成，成功共 {success_count}/{total} 檔！路徑：{target_dir.name}")

    def get_last_batch_skipped_stocks(self) -> list[str]:
        """回傳上次批次導出中被跳過的股票名單"""
        return self._last_batch_skipped_stocks

