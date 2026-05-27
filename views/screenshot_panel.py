"""
截圖面板元件模組
提供日K截圖的預覽、從剪貼簿貼上、選擇圖片檔案與清除功能。
"""

from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QPixmap, QImage, QDragEnterEvent, QDropEvent


class ScreenshotPanel(QWidget):
    """
    日K截圖面板：
    - 支援從剪貼簿貼上（外部 Ctrl+V 觸發）
    - 支援選擇圖片檔案（PNG / JPG / BMP）
    - 支援拖放圖片檔案
    - 顯示縮放預覽
    """

    # 截圖更新信號，帶入 QImage（空表示清除）
    image_changed = pyqtSignal(object)  # QImage | None

    PREVIEW_H = 160  # 預覽區固定高度

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_image: QImage | None = None
        self._setup_ui()
        self.setAcceptDrops(True)

    def _setup_ui(self) -> None:
        """建立截圖面板 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)

        # 標題
        title = QLabel("📷 日K截圖")
        title.setFont(QFont("Microsoft JhengHei", 10, QFont.Weight.Bold))
        title.setStyleSheet("color: #A0C4FF; padding: 2px;")
        layout.addWidget(title)

        # 截圖預覽區
        self._preview = QLabel()
        self._preview.setFixedHeight(self.PREVIEW_H)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._preview.setStyleSheet("""
            QLabel {
                background-color: #0D1B2E;
                border: 1px dashed #2E5D9F;
                border-radius: 4px;
                color: #666688;
                font-family: "Microsoft JhengHei";
                font-size: 9pt;
            }
        """)
        self._preview.setText("尚無截圖\n(Ctrl+V 貼上或點下方按鈕)")
        layout.addWidget(self._preview)

        # 按鈕列
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)

        self._btn_paste  = self._make_btn("📋 貼上", "#2E5D9F", "#4A82D8", tip="從剪貼簿貼上截圖 (Ctrl+V)")
        self._btn_browse = self._make_btn("📂 選擇", "#1B6B3A", "#27AE60", tip="選擇圖片檔案")
        self._btn_clear  = self._make_btn("🗑 清除", "#7D3E3E", "#C0392B", tip="清除截圖")

        btn_layout.addWidget(self._btn_paste)
        btn_layout.addWidget(self._btn_browse)
        btn_layout.addWidget(self._btn_clear)
        layout.addLayout(btn_layout)

        # 連接信號
        self._btn_paste.clicked.connect(self.paste_from_clipboard)
        self._btn_browse.clicked.connect(self.browse_file)
        self._btn_clear.clicked.connect(self.clear_image)

    def _make_btn(self, text: str, bg: str, hover: str, tip: str = "") -> QPushButton:
        """建立統一風格的按鈕"""
        btn = QPushButton(text)
        btn.setFont(QFont("Microsoft JhengHei", 9))
        btn.setToolTip(tip)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 6px;
                font-family: "Microsoft JhengHei";
            }}
            QPushButton:hover {{ background-color: {hover}; }}
            QPushButton:pressed {{ opacity: 0.8; }}
        """)
        return btn

    # ── 公開方法 ───────────────────────────────────────────────

    def paste_from_clipboard(self) -> None:
        """從剪貼簿讀取圖片並顯示預覽"""
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        image = clipboard.image()
        if not image.isNull():
            self._load_image(image)
        else:
            # 嘗試讀取剪貼簿中的檔案路徑
            mime = clipboard.mimeData()
            if mime.hasUrls():
                for url in mime.urls():
                    fp = url.toLocalFile()
                    if Path(fp).suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp"}:
                        self._load_from_file(fp)
                        break

    def browse_file(self) -> None:
        """開啟檔案對話框選擇圖片"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "選擇日K截圖",
            "",
            "圖片檔案 (*.png *.jpg *.jpeg *.bmp);;所有檔案 (*)",
        )
        if file_path:
            self._load_from_file(file_path)

    def clear_image(self) -> None:
        """清除目前的截圖"""
        self._current_image = None
        self._preview.setPixmap(QPixmap())
        self._preview.setText("尚無截圖\n(Ctrl+V 貼上或點下方按鈕)")
        self.image_changed.emit(None)

    def get_image(self) -> QImage | None:
        """回傳目前的截圖 QImage，無截圖時回傳 None"""
        return self._current_image

    def has_image(self) -> bool:
        """回傳是否已有截圖"""
        return self._current_image is not None and not self._current_image.isNull()

    def load_from_qimage(self, image: QImage) -> None:
        """外部提供 QImage 直接載入（供 MainWindow Ctrl+V 呼叫）"""
        if not image.isNull():
            self._load_image(image)

    # ── 拖放支援 ──────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """接受拖放的圖片檔案"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        """處理拖放的圖片檔案"""
        for url in event.mimeData().urls():
            fp = url.toLocalFile()
            if Path(fp).suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp"}:
                self._load_from_file(fp)
                break

    # ── 私有方法 ──────────────────────────────────────────────

    def _load_image(self, image: QImage) -> None:
        """儲存 QImage 並更新預覽"""
        self._current_image = image
        pixmap = QPixmap.fromImage(image)
        scaled = pixmap.scaled(
            QSize(self._preview.width() - 4, self.PREVIEW_H - 4),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview.setPixmap(scaled)
        self._preview.setText("")
        self.image_changed.emit(image)

    def _load_from_file(self, file_path: str) -> None:
        """從檔案路徑載入圖片"""
        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            image = pixmap.toImage()
            self._load_image(image)
