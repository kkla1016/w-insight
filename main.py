"""
台股權證兩階段選股分析系統
程式入口：初始化 QApplication、ConfigManager、AppController 並啟動主視窗。
"""

import sys
import os

# 確保相對路徑從腳本目錄開始
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from utils.config_manager import ConfigManager
from controllers.app_controller import AppController
from views.main_window import MainWindow


def main() -> int:
    """
    應用程式主入口。
    依序初始化設定管理器、控制器、主視窗，並啟動 Qt 事件迴圈。

    Returns:
        Qt 應用程式的退出碼
    """
    # 高 DPI 支援
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("台股權證選股分析系統")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("WarrantTrader")

    # 全域字型：微軟正黑體
    font = QFont("Microsoft JhengHei", 10)
    app.setFont(font)

    # 初始化設定管理器（讀取 config.json）
    config = ConfigManager("config.json")

    # 初始化控制器
    controller = AppController(config)

    # 建立並顯示主視窗
    window = MainWindow(controller)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
