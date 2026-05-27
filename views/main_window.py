"""
主視窗模組
PyQt6 主應用程式視窗，包含工具列、左側面板、三分頁表格與狀態列。
"""

import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
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

    APP_TITLE   = "台股權證兩階段選股分析系統"
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

        self._act_load    = make_action("載入 Excel", "📂", "選擇並載入 Excel 資料檔案", self._on_load)
        self._act_csv     = make_action("匯出 CSV",   "📊", "匯出三階段結果為 CSV 檔案", self._on_export_csv)
        self._act_excel   = make_action("匯出 Excel", "📋", "匯出為多分頁 Excel 檔案",   self._on_export_excel)
        self._act_pdf     = make_action("匯出 PDF 報告", "📄", "生成含截圖的完整分析報告書", self._on_export_pdf)
        self._act_refresh = make_action("重新整理",   "🔄", "重新載入並分析資料",         self._on_refresh)

        for act in [self._act_load, self._act_csv, self._act_excel, self._act_pdf, self._act_refresh]:
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
        
        # 右下：PDF 預覽
        self._pdf_preview = PdfPreviewPanel()
        
        right_panel.addWidget(tab_panel)
        right_panel.addWidget(self._pdf_preview)
        # 預設 1:1 比例
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
        self._ctrl.pdf_preview_ready.connect(self._pdf_preview.load_pdf)
        self._ctrl.stocks_list_ready.connect(self._search_bar.set_stock_list)
        self._ctrl.status_message.connect(self._update_status)
        self._ctrl.error_occurred.connect(self._show_error)
        self._ctrl.export_done.connect(self._on_export_done)

    # ── 事件處理 ──────────────────────────────────────────────

    def _on_load(self) -> None:
        """選擇 Excel 檔案並載入"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "選擇 Excel 資料檔案", "",
            "Excel 檔案 (*.xlsx *.xls);;所有檔案 (*)"
        )
        if file_path:
            self._ctrl.load_and_analyze(file_path)

    def _on_refresh(self) -> None:
        """重新載入目前的 Excel 檔案"""
        self._ctrl.load_and_analyze()

    def _on_search(self, query: str) -> None:
        """股票搜尋觸發，並動態切換分頁標題顯示目前模式"""
        self._current_stock_name = query
        self._ctrl.search_stock(query)
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
        out_dir = QFileDialog.getExistingDirectory(self, "選擇 PDF 儲存目錄", ".")
        if out_dir:
            self._ctrl.export_pdf(
                stock_name=self._current_stock_name,
                output_dir=out_dir,
            )

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
        reply = QMessageBox.question(
            self, "匯出完成",
            f"檔案已儲存：\n{name}\n\n是否開啟所在資料夾？",
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
