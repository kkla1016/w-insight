"""
股票搜尋列元件模組
提供即時搜尋輸入框，含自動補全下拉與清除按鈕。
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit,
    QPushButton, QCompleter, QLabel,
)
from PyQt6.QtCore import Qt, pyqtSignal, QStringListModel
from PyQt6.QtGui import QFont


class StockSearchBar(QWidget):
    """
    股票搜尋列：QLineEdit + QCompleter 自動補全 + 清除按鈕。
    輸入時即時觸發搜尋信號，按 Enter 或從補全清單選擇亦觸發。
    """

    # 搜尋觸發信號，帶入關鍵字字串與是否開啟瀏覽器布林值（空字串表示清除）
    search_triggered = pyqtSignal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """建立搜尋列 UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 標籤
        label = QLabel("🔍 股票搜尋")
        label.setFont(QFont("Microsoft JhengHei", 10, QFont.Weight.Bold))
        label.setStyleSheet("color: #A0C4FF; padding: 2px;")
        layout.addWidget(label)

        # 搜尋輸入框
        self._input = QLineEdit()
        self._input.setPlaceholderText("輸入標的名稱或代號...")
        self._input.setFont(QFont("Microsoft JhengHei", 10))
        self._input.setStyleSheet("""
            QLineEdit {
                background-color: #1E2D45;
                color: #E8EAF0;
                border: 1px solid #2E5D9F;
                border-radius: 4px;
                padding: 4px 8px;
                font-family: "Microsoft JhengHei";
            }
            QLineEdit:focus {
                border: 1px solid #5B9BD5;
            }
        """)
        # 自動補全
        self._completer_model = QStringListModel()
        self._completer = QCompleter(self._completer_model)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._completer.setMaxVisibleItems(10)
        self._input.setCompleter(self._completer)

        layout.addWidget(self._input, 1)

        # 清除按鈕
        self._btn_clear = QPushButton("✕")
        self._btn_clear.setFixedWidth(28)
        self._btn_clear.setToolTip("清除搜尋，回到全部資料")
        self._btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #C0392B;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 11pt;
            }
            QPushButton:hover { background-color: #E74C3C; }
            QPushButton:pressed { background-color: #962D22; }
        """)
        layout.addWidget(self._btn_clear)

        # 連接信號
        self._input.textChanged.connect(self._on_text_changed)
        self._input.returnPressed.connect(self._on_search)
        self._completer.activated.connect(self._on_completer_activated)
        self._btn_clear.clicked.connect(self._on_clear)

    def set_stock_list(self, names: list[str]) -> None:
        """
        更新自動補全的股票名稱清單。

        Args:
            names: 股票名稱字串清單
        """
        self._completer_model.setStringList(names)

    def get_query(self) -> str:
        """回傳目前輸入框的文字內容"""
        return self._input.text().strip()

    def _on_text_changed(self, text: str) -> None:
        """輸入變更時即時觸發搜尋（不自動開瀏覽器）"""
        self.search_triggered.emit(text.strip(), False)

    def _on_search(self) -> None:
        """按 Enter 時觸發搜尋（開啟瀏覽器）"""
        self.search_triggered.emit(self.get_query(), True)

    def _on_completer_activated(self, text: str) -> None:
        """從自動補全清單選擇時觸發搜尋（開啟瀏覽器）"""
        self.search_triggered.emit(text.strip(), True)

    def _on_clear(self) -> None:
        """清除輸入框並觸發空白搜尋（不開啟瀏覽器）"""
        self._input.clear()
        self.search_triggered.emit("", False)
