"""
主視窗模組
PyQt6 主應用程式視窗，包含工具列、左側面板、三分頁表格與狀態列。
"""

import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QGroupBox, QWidget, QHBoxLayout, QVBoxLayout,
    QTabWidget, QToolBar, QStatusBar, QLabel,
    QFileDialog, QMessageBox, QSplitter, QApplication,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QAction, QIcon, QFont, QKeySequence, QKeyEvent, QColor

from views.warrant_table import WarrantTableView
from views.stock_search_bar import StockSearchBar
from views.screenshot_panel import ScreenshotPanel
from views.pdf_preview_panel import PdfPreviewPanel


class MainWindow(QMainWindow):
    """
    應用程式主視窗，負責組裝所有 View 元件並連接 Controller 信號。
    """

    APP_TITLE   = "W-Insight (權證洞察)"
    APP_VERSION = "v1.0.0"
    WIN_MIN_W   = 1100
    WIN_MIN_H   = 700

    def __init__(self, controller, parent=None):
        """
        Args:
            controller: AppController 實例
            parent: Qt 父物件
        """
        super().__init__(parent)
        self._ctrl = controller
        self._current_stock_name = ""  # 用於 PDF 報告的標的名稱

        self._setup_window()
        self._setup_style()
        self._setup_toolbar()
        self._setup_central_widget()
        self._setup_statusbar()
        self._connect_controller_signals()

        # 啟動時自動載入資料
        self._ctrl.load_and_analyze()

    # ── 初始化 ─────────────────────────────────────────────────

    def _setup_window(self) -> None:
        """設定視窗基本屬性"""
        self.setWindowTitle(f"{self.APP_TITLE}  {self.APP_VERSION}")
        self.setMinimumSize(self.WIN_MIN_W, self.WIN_MIN_H)
        self.resize(1280, 800)

    def _setup_style(self) -> None:
        """套用全域深色金融主題"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0F1923;
            }
            QWidget {
                background-color: #0F1923;
                color: #E8EAF0;
                font-family: "Microsoft JhengHei";
            }
            QTabWidget::pane {
                border: 1px solid #2A3F5F;
                background-color: #111E2E;
            }
            QTabBar::tab {
                background-color: #1B3A6B;
                color: #A0C4FF;
                padding: 8px 20px;
                border: 1px solid #2A3F5F;
                border-bottom: none;
                font-family: "Microsoft JhengHei";
                font-size: 10pt;
                font-weight: bold;
                min-width: 120px;
            }
            QTabBar::tab:selected {
                background-color: #2E5D9F;
                color: #FFFFFF;
            }
            QTabBar::tab:hover:!selected {
                background-color: #244982;
            }
            QToolBar {
                background-color: #0D1B2E;
                border-bottom: 1px solid #1B3A6B;
                spacing: 4px;
                padding: 4px;
            }
            QStatusBar {
                background-color: #0D1B2E;
                color: #7FA8D8;
                font-family: "Microsoft JhengHei";
                font-size: 9pt;
                border-top: 1px solid #1B3A6B;
            }
            QSplitter::handle {
                background-color: #1B3A6B;
                width: 2px;
            }
            QMessageBox {
                background-color: #111E2E;
            }
        """)

    def _setup_toolbar(self) -> None:
        """建立頂部工具列"""
        tb = QToolBar("主工具列")
        tb.setMovable(False)
        tb.setIconSize(QSize(20, 20))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(tb)

        def make_action(label: str, icon_char: str, tooltip: str, callback) -> QAction:
            act = QAction(f"{icon_char}  {label}", self)
            act.setToolTip(tooltip)
            act.triggered.connect(callback)
            return act

        self._act_load    = make_action("Excel 檔案路徑設定", "📂", "設定四合一資料夾路徑與智慧檢索", self._on_open_path_config_dialog)
        self._act_csv     = make_action("匯出 CSV",   "📊", "匯出三階段結果為 CSV 檔案", self._on_export_csv)
        self._act_excel   = make_action("匯出 Excel", "📋", "匯出為多分頁 Excel 檔案",   self._on_export_excel)
        self._act_pdf     = make_action("匯出 PDF 報告", "📄", "生成含截圖的完整分析報告書", self._on_export_pdf)
        self._act_batch_pdf = make_action("批次匯出 PDF 報告", "📦", "一鍵依 Excel 名單全自動分類輸出", self._on_export_batch_pdf)
        self._act_refresh = make_action("重新整理",   "🔄", "重新載入並分析資料",         self._on_refresh)

        for act in [self._act_load, self._act_csv, self._act_excel, self._act_pdf, self._act_batch_pdf, self._act_refresh]:
            self._style_action(act)
            tb.addAction(act)
            tb.addSeparator()

        # 工具列按鈕樣式
        self.setStyleSheet(self.styleSheet() + """
            QToolButton {
                background-color: #1B3A6B;
                color: #E8EAF0;
                border: 1px solid #2A3F5F;
                border-radius: 4px;
                padding: 5px 12px;
                font-family: "Microsoft JhengHei";
                font-size: 10pt;
            }
            QToolButton:hover  { background-color: #2E5D9F; }
            QToolButton:pressed { background-color: #1B3A6B; }
        """)

    def _style_action(self, act: QAction) -> None:
        """為 Action 加上字體設定"""
        pass  # 樣式由 QToolButton 統一管理

    def _setup_central_widget(self) -> None:
        """建立主體區域：左側面板 + 右側分頁表格"""
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左側面板
        left_panel = self._build_left_panel()
        left_panel.setMinimumWidth(200)
        left_panel.setMaximumWidth(280)

        # 右側主區域（垂直分隔：上欄權證資訊，下欄 PDF 預覽）
        right_panel = QSplitter(Qt.Orientation.Vertical)
        
        # 右上：分頁表格
        tab_panel = self._build_tab_panel()
        
        # 右下：PDF 雙欄預覽 (1:1)
        pdf_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._pdf_preview_v1 = PdfPreviewPanel("📄 原版報告書即時預覽")
        self._pdf_preview_v2 = PdfPreviewPanel("🏆 V2.0 版報告書即時預覽")
        pdf_splitter.addWidget(self._pdf_preview_v1)
        pdf_splitter.addWidget(self._pdf_preview_v2)
        pdf_splitter.setSizes([500, 500])
        pdf_splitter.setChildrenCollapsible(False)
        
        right_panel.addWidget(tab_panel)
        right_panel.addWidget(pdf_splitter)
        # 預設上下 1:1 比例
        right_panel.setSizes([400, 400])
        right_panel.setChildrenCollapsible(False)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([240, 1040])
        splitter.setChildrenCollapsible(False)

        self.setCentralWidget(splitter)

    def _build_left_panel(self) -> QWidget:
        """建立左側面板（搜尋列 + 截圖面板）"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 4, 8)
        layout.setSpacing(12)

        # 股票搜尋列
        self._search_bar = StockSearchBar()
        self._search_bar.search_triggered.connect(self._on_search)
        layout.addWidget(self._search_bar)

        # 分隔線
        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #2A3F5F;")
        layout.addWidget(sep)

        # 截圖面板
        self._screenshot_panel = ScreenshotPanel()
        self._screenshot_panel.image_changed.connect(self._on_screenshot_changed)
        layout.addWidget(self._screenshot_panel)

        # 1. V1.0 (V0) 評價標準 GroupBox
        group_v0 = QGroupBox("📊 V1.0 (V0) 權證評價標準 (滿分 100)")
        group_v0.setStyleSheet("""
            QGroupBox {
                border: 1px solid #1B3A6B;
                border-radius: 6px;
                margin-top: 10px;
                font-size: 8.5pt;
                font-weight: bold;
                color: #A0C4FF;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 4px;
                background-color: #111E2E;
            }
        """)
        v0_layout = QVBoxLayout(group_v0)
        v0_layout.setContentsMargins(8, 12, 8, 8)
        v0_text = QLabel(
            "• <b>Delta 適切度 (25分)</b>：越接近 0.5 越高<br/>"
            "• <b>剩餘天期 (20分)</b>：180 天以上得滿分<br/>"
            "• <b>有效槓桿 (20分)</b>：10x 以上得滿分<br/>"
            "• <b>IV/HV 品質 (20分)</b>：1.0 最佳，>1.5 得 0分<br/>"
            "• <b>流動性 (15分)</b>：日成交量 1,000張得滿分"
        )
        v0_text.setFont(QFont("Microsoft JhengHei", 8))
        v0_text.setStyleSheet("color: #BACAD6; line-height: 130%;")
        v0_text.setTextFormat(Qt.TextFormat.RichText)
        v0_text.setWordWrap(True)
        v0_layout.addWidget(v0_text)
        layout.addWidget(group_v0)

        # 2. V2.0 評價標準 GroupBox
        group_v2 = QGroupBox("🏆 V2.0 權證評價標準 (滿分 100)")
        group_v2.setStyleSheet("""
            QGroupBox {
                border: 1px solid #1B3A6B;
                border-radius: 6px;
                margin-top: 10px;
                font-size: 8.5pt;
                font-weight: bold;
                color: #F1C40F;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 4px;
                background-color: #111E2E;
            }
        """)
        v2_layout = QVBoxLayout(group_v2)
        v2_layout.setContentsMargins(8, 12, 8, 8)
        v2_text = QLabel(
            "• <b>A. 現股結構 (25分)</b>：基礎 15分 + ROI 加分<br/>"
            "• <b>B. 權證品質 (35分)</b>：基礎 25分 + IV/HV 抄擺<br/>"
            "• <b>C. 爆發能力 (20分)</b>：Delta 區間 + G/T 比值<br/>"
            "• <b>D. 交易安全 (20分)</b>：天期 >= 90天 + 成交金額"
        )
        v2_text.setFont(QFont("Microsoft JhengHei", 8))
        v2_text.setStyleSheet("color: #BACAD6; line-height: 130%;")
        v2_text.setTextFormat(Qt.TextFormat.RichText)
        v2_text.setWordWrap(True)
        v2_layout.addWidget(v2_text)
        layout.addWidget(group_v2)

        layout.addStretch()

        # 版本標籤
        ver_label = QLabel(self.APP_VERSION)
        ver_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver_label.setStyleSheet("color: #3A5F8A; font-size: 8pt;")
        layout.addWidget(ver_label)

        panel.setStyleSheet("background-color: #111E2E; border-right: 1px solid #1B3A6B;")
        return panel

    def _build_tab_panel(self) -> QTabWidget:
        """建立三分頁表格（階段一、階段二、IV 警示）"""
        self._tabs = QTabWidget()

        # 取得 Tooltip 字典
        strategy = self._ctrl.get_strategy()
        tooltip_keys = ["DELTA", "GAMMA", "THETA", "VEGA", "IV_HV_ratio", "有效槓桿", "剩餘期間(日)"]
        tooltips = {k: strategy.get_greek_tooltip(k) for k in tooltip_keys}

        # 階段一分頁
        self._table_p1 = WarrantTableView(tooltips=tooltips)
        self._tabs.addTab(self._table_p1, "⚡ 階段一：突破建倉")

        # 階段二分頁
        self._table_p2 = WarrantTableView(tooltips=tooltips)
        self._tabs.addTab(self._table_p2, "🚀 階段二：主升加碼")

        # IV 警示分頁
        self._table_warn = WarrantTableView(tooltips=tooltips)
        self._tabs.addTab(self._table_warn, "⚠️ IV 異常警示")

        # V2 A級分頁
        self._table_v2_a = WarrantTableView(tooltips=tooltips)
        self._tabs.addTab(self._table_v2_a, "🏆 V2.0 主力攻擊型 (A級)")

        # V2 B級分頁
        self._table_v2_b = WarrantTableView(tooltips=tooltips)
        self._tabs.addTab(self._table_v2_b, "📈 V2.0 穩健趨勢型 (B級)")

        return self._tabs

    def _setup_statusbar(self) -> None:
        """建立底部狀態列"""
        self._status_bar = QStatusBar()
        self._status_label = QLabel("就緒，請等待資料載入...")
        self._status_label.setFont(QFont("Microsoft JhengHei", 9))
        self._status_bar.addWidget(self._status_label, 1)
        self.setStatusBar(self._status_bar)

    # ── Controller 信號連接 ───────────────────────────────────

    def _connect_controller_signals(self) -> None:
        """連接 Controller 發出的所有 Qt 信號"""
        self._ctrl.data_loaded.connect(self._on_data_loaded)
        self._ctrl.phase1_updated.connect(self._table_p1.load_dataframe)
        self._ctrl.phase2_updated.connect(self._table_p2.load_dataframe)
        self._ctrl.warnings_updated.connect(self._table_warn.load_dataframe)
        self._ctrl.v2_class_a_updated.connect(self._table_v2_a.load_dataframe)
        self._ctrl.v2_class_b_updated.connect(self._table_v2_b.load_dataframe)
        self._ctrl.pdf_preview_ready.connect(self._pdf_preview_v1.load_pdf)
        # 將等待 controller 加入 pdf_v2_preview_ready 信號
        if hasattr(self._ctrl, 'pdf_v2_preview_ready'):
            self._ctrl.pdf_v2_preview_ready.connect(self._pdf_preview_v2.load_pdf)
        self._ctrl.stocks_list_ready.connect(self._search_bar.set_stock_list)
        self._ctrl.status_message.connect(self._update_status)
        self._ctrl.error_occurred.connect(self._show_error)
        self._ctrl.export_done.connect(self._on_export_done)
        self._ctrl.batch_progress.connect(self._on_batch_progress)
        self._ctrl.batch_done.connect(self._on_batch_done)


    # ── 事件處理 ──────────────────────────────────────────────

    def _on_open_path_config_dialog(self) -> None:
        """開啟 Excel 檔案路徑設定對話框"""
        dialog = PathConfigDialog(self._ctrl, self)
        dialog.exec()

    def _on_refresh(self) -> None:
        """重新載入目前的 Excel 檔案"""
        self._ctrl.load_and_analyze()

    def _on_search(self, query: str, open_browser: bool = False) -> None:
        """股票搜尋觸發，並動態切換分頁標題顯示目前模式"""
        self._current_stock_name = query
        self._ctrl.search_stock(query, open_browser=open_browser)
        self._update_tab_titles(query)

    def _on_screenshot_changed(self, image) -> None:
        """截圖更新時通知 Controller"""
        if image is not None:
            self._ctrl.set_screenshot(image)
        else:
            self._ctrl.clear_screenshot()

    def _on_export_csv(self) -> None:
        """匯出 CSV"""
        out_dir = QFileDialog.getExistingDirectory(self, "選擇匯出目錄", ".")
        if out_dir:
            self._ctrl.export_csv(out_dir)

    def _on_export_excel(self) -> None:
        """匯出 Excel"""
        out_dir = QFileDialog.getExistingDirectory(self, "選擇匯出目錄", ".")
        if out_dir:
            self._ctrl.export_excel(out_dir)

    def _on_export_pdf(self) -> None:
        """匯出 PDF 報告書"""
        default_dir = self._ctrl._config.get_output_dir()
        out_dir = QFileDialog.getExistingDirectory(self, "選擇 PDF 儲存目錄", default_dir)
        if out_dir:
            self._ctrl.export_pdf(
                stock_name=self._current_stock_name,
                output_dir=out_dir,
            )

    def _on_export_batch_pdf(self) -> None:
        """一鍵批次全自動匯出報告書，跳過手動目錄指定，直接觸發自動日期建檔"""
        from PyQt6.QtWidgets import QProgressDialog
        
        # 1. 安全檢查：是否有指定名單與輸出資料夾
        batch_folder = self._ctrl._config.get_batch_stock_folder()
        if not batch_folder or not os.path.exists(batch_folder):
            self._show_error("請先在『Excel 檔案路徑設定』中指定『批次輸出股票名單資料夾』位置。")
            return
            
        # 2. 建立並彈出 QProgressDialog
        self._progress_dialog = QProgressDialog("正在準備批次匯出 PDF 報告書...", "取消", 0, 100, self)
        self._progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress_dialog.setWindowTitle("批次匯出 PDF 報告書")
        self._progress_dialog.setMinimumDuration(0)
        self._progress_dialog.setValue(0)
        self._progress_dialog.show()
        
        # 3. 呼叫控制器執行批次
        self._ctrl.export_batch_pdf()
        
    def _on_batch_progress(self, current: int, total: int, stock_name: str) -> None:
        """批次進度槽函數：即時刷新流暢進度條，並偵測取消動作"""
        if hasattr(self, '_progress_dialog') and self._progress_dialog:
            if self._progress_dialog.wasCanceled():
                self._ctrl.cancel_batch_pdf()
                self._progress_dialog.close()
                self._progress_dialog = None
                return
                
            pct = int((current - 1) / total * 100)
            self._progress_dialog.setValue(pct)
            self._progress_dialog.setLabelText(f"正在生成 ({current}/{total}): {stock_name} ...")
            QApplication.processEvents() # 驅動 Qt 事件循環，保證 UI 零凍結絲滑刷新
            
    def _on_batch_done(self, count: int, target_dir: str) -> None:
        """批次完成槽函數：詢問是否跳轉直達該日期子資料夾"""
        # 讀取被跳過的股票清單
        skipped = self._ctrl.get_last_batch_skipped_stocks()
        self._skipped_info = f"\n\n（注意：有 {len(skipped)} 檔股票在資料庫中查無認購權證而被安全跳過：\n{', '.join(skipped)}）" if skipped else ""

        if hasattr(self, '_progress_dialog') and self._progress_dialog:
            self._progress_dialog.setValue(100)
            self._progress_dialog.close()
            self._progress_dialog = None
            
        reply = QMessageBox.question(
             self, "批次匯出完成",
             f"批次輸出結束！\n已成功為 {count} 檔股票建立雙版本 PDF 報告書。{self._skipped_info}\n\n是否開啟當日日期資料夾？\n{Path(target_dir).name}",
             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            os.startfile(target_dir)


    def _on_data_loaded(self, date_str: str, count: int) -> None:
        """資料載入完成後更新視窗標題並重設分頁標題"""
        self.setWindowTitle(
            f"{self.APP_TITLE}  {self.APP_VERSION}  ─  {date_str}（共 {count} 筆認購）"
        )
        # 重設分頁標題（載入新資料時清除個股模式標示）
        self._update_tab_titles("")

    def _on_export_done(self, file_path: str) -> None:
        """匯出完成後提示並詢問是否開啟資料夾"""
        name = Path(file_path).name
        
        # 若是 PDF 報告，因為同時生成了原版與 V2.0，給出雙版提示
        if name.endswith(".pdf"):
            if "_v2" in name:
                v1_name = name.replace("_v2", "")
                v2_name = name
            else:
                v1_name = name
                v2_name = name.replace(".pdf", "_v2.pdf")
            msg = f"原版與 V2.0 報告書均已成功儲存：\n1. {v1_name}\n2. {v2_name}\n\n是否開啟所在資料夾？"
        else:
            msg = f"檔案已儲存：\n{name}\n\n是否開啟所在資料夾？"
            
        reply = QMessageBox.question(
            self, "匯出完成",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            folder = str(Path(file_path).parent)
            os.startfile(folder)

    def _update_status(self, message: str) -> None:
        """更新狀態列訊息"""
        self._status_label.setText(message)

    def _update_tab_titles(self, query: str) -> None:
        """
        依搜尋模式動態更新分頁標題。
        - 有搜尋關鍵字：顯示「個股模式」及標的名稱
        - 無搜尋關鍵字：回到全市場模式標題
        """
        if query.strip():
            # 個股分析模式：標題加上標的名稱
            name = query.strip()
            self._tabs.setTabText(0, f"⚡ 建倉推薦 [{name}]")
            self._tabs.setTabText(1, f"🚀 加碼推薦 [{name}]")
            self._tabs.setTabText(2, f"⚠️ IV 分析 [{name}]")
        else:
            # 全市場模式：回到預設標題
            self._tabs.setTabText(0, "⚡ 階段一：突破建倉")
            self._tabs.setTabText(1, "🚀 階段二：主升加碼")
            self._tabs.setTabText(2, "⚠️ IV 異常警示")

    def _show_error(self, message: str) -> None:
        """顯示錯誤對話框"""
        QMessageBox.critical(self, "錯誤", message)
        self._update_status(f"❌ {message}")

    # ── 全域鍵盤事件 ─────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """
        處理全域鍵盤事件：
        - Ctrl+V：嘗試從剪貼簿貼上截圖
        - F5：重新載入資料
        """
        if event.matches(QKeySequence.StandardKey.Paste):
            self._screenshot_panel.paste_from_clipboard()
        elif event.key() == Qt.Key.Key_F5:
            self._on_refresh()
        else:
            super().keyPressEvent(event)


from PyQt6.QtWidgets import QDialog, QGridLayout, QLabel, QLineEdit, QPushButton

class PathConfigDialog(QDialog):
    """
    Excel 四合一檔案路徑設定對話框（已升級為 6 合 1，新增批次名單與預設 PDF 目錄設定）。
    支援設定六個核心資料夾，並以深色金融主題渲染。
    """
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self._ctrl = controller
        self._config = controller._config
        self.setWindowTitle("Excel 檔案路徑設定")
        self.setMinimumWidth(580)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # 總說明標籤
        lbl_title = QLabel("📂 Excel 檔案路徑與 PDF 存放設定")
        lbl_title.setStyleSheet("color: #A0C4FF; font-size: 11pt; font-weight: bold;")
        layout.addWidget(lbl_title)

        # 網格佈局
        grid = QGridLayout()
        grid.setSpacing(10)

        # 設定項目
        self._inputs = {}
        
        items = [
            ("warrant", "權證每日交易EXCEL資料夾:", self._config.get_excel_folder, "folder"),
            ("institutional", "三大法人每日買賣超EXCEL資料夾:", self._config.get_folder_institutional, "folder"),
            ("unadjusted_price", "未調整股價(日)EXCEL資料夾 [第一優先]:", self._config.get_folder_unadjusted_price, "folder"),
            ("daily_price", "日均價DATA EXCEL資料夾 [第二優先]:", self._config.get_folder_daily_price, "folder"),
            ("foreign_ownership", "外資法人持股EXCEL資料夾:", self._config.get_folder_foreign_ownership, "folder"),
            ("batch_folder", "批次輸出股票名單資料夾:", self._config.get_batch_stock_folder, "folder"),
            ("output_dir", "預設 PDF 報告存放資料夾:", self._config.get_output_dir, "folder")
        ]

        for i, (key, label, getter, item_type) in enumerate(items):
            # 建立按鈕
            btn = QPushButton(label)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #1B3A6B;
                    color: #E8EAF0;
                    border: 1px solid #2A3F5F;
                    border-radius: 4px;
                    padding: 6px 12px;
                    font-weight: bold;
                    font-size: 9pt;
                    text-align: left;
                    min-width: 220px;
                }
                QPushButton:hover {
                    background-color: #2E5D9F;
                }
            """)
            if item_type == "folder":
                btn.clicked.connect(lambda checked, k=key: self._on_select_folder(k))
            else:
                btn.clicked.connect(lambda checked, k=key: self._on_select_file(k))
            grid.addWidget(btn, i, 0)

            # 建立輸入框
            edit = QLineEdit(getter())
            edit.setReadOnly(True)
            edit.setStyleSheet("""
                QLineEdit {
                    background-color: #0D1B2E;
                    color: #7FA8D8;
                    border: 1px solid #1B3A6B;
                    border-radius: 4px;
                    padding: 6px;
                    font-size: 9pt;
                }
            """)
            grid.addWidget(edit, i, 1)
            self._inputs[key] = edit

        layout.addLayout(grid)

        # 說明提示
        lbl_tip = QLabel("💡 批次匯出時系統會自動於預設 PDF 存放資料夾下建立當日日期子資料夾。")
        lbl_tip.setStyleSheet("color: #7FA8D8; font-size: 8.5pt; font-style: italic;")
        layout.addWidget(lbl_tip)

        # 底部按鈕
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._btn_save = QPushButton("儲存設定")
        self._btn_save.setStyleSheet("""
            QPushButton {
                background-color: #2E5D9F;
                color: #FFFFFF;
                border: 1px solid #3A7DCE;
                border-radius: 4px;
                padding: 6px 20px;
                font-weight: bold;
                font-size: 9.5pt;
            }
            QPushButton:hover {
                background-color: #3D75C2;
            }
        """)
        self._btn_save.clicked.connect(self._on_save)

        self._btn_cancel = QPushButton("取消")
        self._btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #2A3F5F;
                color: #E8EAF0;
                border: 1px solid #3B5A87;
                border-radius: 4px;
                padding: 6px 20px;
                font-size: 9.5pt;
            }
            QPushButton:hover {
                background-color: #355078;
            }
        """)
        self._btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(self._btn_save)
        btn_layout.addWidget(self._btn_cancel)
        layout.addLayout(btn_layout)

        # 視窗樣式與主視窗一致
        self.setStyleSheet("""
            QDialog {
                background-color: #111E2E;
                border: 1px solid #1B3A6B;
            }
            QLabel {
                background-color: transparent;
            }
        """)

    def _on_select_folder(self, key: str) -> None:
        from PyQt6.QtWidgets import QFileDialog
        current_dir = self._inputs[key].text()
        folder_path = QFileDialog.getExistingDirectory(self, "選擇資料夾", current_dir)
        if folder_path:
            folder_path = folder_path.replace("\\", "/")
            self._inputs[key].setText(folder_path)

    def _on_select_file(self, key: str) -> None:
        from PyQt6.QtWidgets import QFileDialog
        current_val = self._inputs[key].text()
        current_dir = str(Path(current_val).parent) if current_val else "."
        file_path, _ = QFileDialog.getOpenFileName(self, "選擇批次名單 Excel", current_dir, "Excel 檔案 (*.xlsx *.xls)")
        if file_path:
            file_path = file_path.replace("\\", "/")
            self._inputs[key].setText(file_path)

    def _on_save(self) -> None:
        # 將設定寫入 Config
        self._config.set_excel_folder(self._inputs["warrant"].text())
        self._config.set_folder_institutional(self._inputs["institutional"].text())
        self._config.set_folder_unadjusted_price(self._inputs["unadjusted_price"].text())
        self._config.set_folder_daily_price(self._inputs["daily_price"].text())
        self._config.set_folder_foreign_ownership(self._inputs["foreign_ownership"].text())
        self._config.set_batch_stock_folder(self._inputs["batch_folder"].text())
        self._config.set_output_dir(self._inputs["output_dir"].text())
        
        # 觸發 Controller 重新讀取核心權證 Excel
        self._ctrl.load_and_analyze(self._inputs["warrant"].text())
        self.accept()

