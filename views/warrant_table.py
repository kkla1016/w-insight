"""
資料表格元件模組
提供 PandasTableModel 與 WarrantTableView，
支援點擊欄位排序、條件色彩格式化與 Tooltip 顯示。
"""

import pandas as pd
from PyQt6.QtCore import (
    Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel
)
from PyQt6.QtGui import QColor, QFont, QBrush
from PyQt6.QtWidgets import QTableView, QAbstractItemView, QHeaderView


class PandasTableModel(QAbstractTableModel):
    """
    將 pandas DataFrame 橋接至 Qt 的 MVC 表格模型。
    支援資料格式化、條件背景色與 Tooltip 資料角色。
    """

    # 正值欄位（ROI%、槓桿等）超過 0 時標綠色
    POSITIVE_COLS = {"標的證券ROI%", "有效槓桿", "權證ROI(%)"}
    # 負值欄位（THETA）標橘色提醒
    NEGATIVE_COLS = {"THETA"}
    # IV/HV 欄位需特殊色彩處理
    IV_HV_COL = "IV_HV_ratio"

    # 色彩定義
    COLOR_POSITIVE    = QColor("#1B8A3C")   # 深綠
    COLOR_NEGATIVE    = QColor("#C0392B")   # 深紅
    COLOR_WARN_ORANGE = QColor("#E67E22")   # 橘（注意）
    COLOR_WARN_RED    = QColor("#C0392B")   # 紅（高風險）
    COLOR_NORMAL      = QColor("#1B3A6B")   # 深藍（正常）
    COLOR_ROW_ODD     = QColor("#1E2D45")   # 深藍灰（奇數列背景）
    COLOR_ROW_EVEN    = QColor("#172236")   # 更深藍（偶數列背景）
    COLOR_HEADER_BG   = QColor("#0D1B2E")   # 標題背景
    COLOR_TEXT        = QColor("#E8EAF0")   # 淺灰文字

    def __init__(self, df: pd.DataFrame = None, tooltips: dict = None, parent=None):
        """
        Args:
            df: 要顯示的 DataFrame
            tooltips: {欄位名: 說明文字} 的字典，供標題 Tooltip 使用
            parent: Qt 父物件
        """
        super().__init__(parent)
        self._df = df if df is not None else pd.DataFrame()
        self._tooltips = tooltips or {}

    def update_data(self, df: pd.DataFrame) -> None:
        """更新表格資料並通知 View 重繪"""
        self.beginResetModel()
        self._df = df if df is not None else pd.DataFrame()
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._df)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self._df.columns)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        row, col = index.row(), index.column()
        col_name = self._df.columns[col]
        value = self._df.iloc[row, col]

        if role == Qt.ItemDataRole.DisplayRole:
            return self._format_value(col_name, value)

        if role == Qt.ItemDataRole.ForegroundRole:
            return self._get_foreground(col_name, value)

        if role == Qt.ItemDataRole.BackgroundRole:
            bg = self.COLOR_ROW_ODD if row % 2 == 0 else self.COLOR_ROW_EVEN
            return QBrush(bg)

        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignCenter)

        if role == Qt.ItemDataRole.FontRole:
            font = QFont("Microsoft JhengHei", 9)
            return font

        return None

    def headerData(self, section: int, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal:
            if role == Qt.ItemDataRole.DisplayRole:
                return self._df.columns[section] if section < len(self._df.columns) else ""
            if role == Qt.ItemDataRole.ToolTipRole:
                col = self._df.columns[section] if section < len(self._df.columns) else ""
                return self._tooltips.get(col, "")
            if role == Qt.ItemDataRole.ForegroundRole:
                return QBrush(QColor("#FFFFFF"))
            if role == Qt.ItemDataRole.BackgroundRole:
                return QBrush(self.COLOR_HEADER_BG)
            if role == Qt.ItemDataRole.FontRole:
                font = QFont("Microsoft JhengHei", 9)
                font.setBold(True)
                return font
        if orientation == Qt.Orientation.Vertical:
            if role == Qt.ItemDataRole.DisplayRole:
                return section + 1
        return None

    def _format_value(self, col_name: str, value) -> str:
        """格式化顯示值"""
        if pd.isna(value):
            return "-"
        if isinstance(value, float):
            return f"{value:.2f}"
        return str(value)

    def _get_foreground(self, col_name: str, value) -> QBrush | None:
        """依欄位名稱與數值決定文字顏色"""
        if pd.isna(value):
            return QBrush(QColor("#666666"))

        if col_name == self.IV_HV_COL:
            try:
                v = float(value)
                if v > 1.5:
                    return QBrush(self.COLOR_WARN_RED)
                elif v > 1.3:
                    return QBrush(self.COLOR_WARN_ORANGE)
                else:
                    return QBrush(self.COLOR_NORMAL)
            except (ValueError, TypeError):
                pass

        if col_name in self.POSITIVE_COLS:
            try:
                v = float(value)
                if v > 0:
                    return QBrush(self.COLOR_POSITIVE)
                elif v < 0:
                    return QBrush(self.COLOR_NEGATIVE)
            except (ValueError, TypeError):
                pass

        return QBrush(self.COLOR_TEXT)


class WarrantTableView(QTableView):
    """
    自定義 QTableView：整合 PandasTableModel 與 QSortFilterProxyModel，
    提供欄位排序、欄寬自適應與深色主題樣式。
    """

    def __init__(self, tooltips: dict = None, parent=None):
        """
        Args:
            tooltips: 欄位 Tooltip 字典
            parent: Qt 父物件
        """
        super().__init__(parent)
        self._source_model = PandasTableModel(tooltips=tooltips)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._source_model)
        self.setModel(self._proxy)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """設定表格外觀與行為"""
        # 允許欄位排序
        self.setSortingEnabled(True)
        self.horizontalHeader().setSortIndicatorShown(True)

        # 選取整行
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        # 欄寬自適應
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        header.setDefaultSectionSize(90)
        header.setMinimumSectionSize(60)

        # 列高
        self.verticalHeader().setDefaultSectionSize(24)
        self.verticalHeader().setVisible(False)

        # 交替列色、無框線
        self.setAlternatingRowColors(False)
        self.setShowGrid(True)
        self.setGridStyle(Qt.PenStyle.SolidLine)

        # 深色主題樣式
        self.setStyleSheet("""
            QTableView {
                background-color: #172236;
                color: #E8EAF0;
                border: 1px solid #2A3F5F;
                gridline-color: #2A3F5F;
                font-family: "Microsoft JhengHei";
                font-size: 9pt;
            }
            QHeaderView::section {
                background-color: #0D1B2E;
                color: #FFFFFF;
                border: 1px solid #2A3F5F;
                padding: 4px;
                font-weight: bold;
                font-family: "Microsoft JhengHei";
            }
            QHeaderView::section:hover {
                background-color: #1B3A6B;
            }
            QTableView::item:selected {
                background-color: #2E5D9F;
                color: #FFFFFF;
            }
            QScrollBar:vertical {
                background: #0D1B2E;
                width: 10px;
            }
            QScrollBar::handle:vertical {
                background: #2A3F5F;
                border-radius: 5px;
            }
        """)

    def load_dataframe(self, df: pd.DataFrame) -> None:
        """載入新的 DataFrame 並重繪表格"""
        self._source_model.update_data(df)
        # 重設排序
        self._proxy.invalidate()
        self.resizeColumnsToContents()
        # 確保最後欄延伸到邊界
        header = self.horizontalHeader()
        if header.count() > 0:
            header.setStretchLastSection(True)
