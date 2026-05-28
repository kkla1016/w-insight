"""
PDF 預覽面板模組
使用 PyMuPDF (fitz) 渲染 PDF 文件並顯示於 QScrollArea 內。
"""

import fitz  # PyMuPDF
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QLabel, 
    QApplication, QSizePolicy
)
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import Qt

class PdfPreviewPanel(QWidget):
    """
    接收 PDF 檔案路徑，並將其每一頁渲染為圖片顯示在可捲動的區域中。
    """
    
    def __init__(self, title: str = "📄 報告書即時預覽", parent=None):
        super().__init__(parent)
        self._title = title
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 標題列
        self.title_label = QLabel(self._title)
        self.title_label.setStyleSheet("""
            color: #A0C4FF;
            background-color: #0D1B2E;
            padding: 8px;
            font-weight: bold;
            font-size: 10pt;
            border-bottom: 1px solid #1B3A6B;
        """)
        layout.addWidget(self.title_label)

        # 捲動區
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea { border: none; background-color: #111E2E; }
        """)

        # 內容容器
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background-color: #111E2E;")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.content_layout.setSpacing(10)
        self.content_layout.setContentsMargins(10, 10, 10, 10)

        self.scroll_area.setWidget(self.content_widget)
        layout.addWidget(self.scroll_area)

    def load_pdf(self, file_path: str) -> None:
        """
        載入並渲染 PDF。
        
        Args:
            file_path: PDF 檔案路徑
        """
        # 清除舊內容
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not file_path:
            return

        try:
            doc = fitz.open(file_path)
            # 設定放大比例（矩陣），讓圖片較清晰
            zoom_matrix = fitz.Matrix(1.5, 1.5)
            
            for page in doc:
                pix = page.get_pixmap(matrix=zoom_matrix)
                
                # 轉換為 QImage
                img = QImage(
                    pix.samples, 
                    pix.width, 
                    pix.height, 
                    pix.stride, 
                    QImage.Format.Format_RGB888
                )
                
                # 放入 QLabel
                label = QLabel()
                label.setPixmap(QPixmap.fromImage(img))
                # 加個白邊和陰影效果（直接用 stylesheet）
                label.setStyleSheet("border: 1px solid #000; background-color: white;")
                self.content_layout.addWidget(label)
                
            doc.close()
            
        except Exception as e:
            err_label = QLabel(f"PDF 預覽載入失敗：{e}")
            err_label.setStyleSheet("color: red; padding: 20px;")
            self.content_layout.addWidget(err_label)
