@echo off
title 啟動 W-Insight 權證洞察系統
echo ===================================================
echo   正在為您啟動 W-Insight 權證洞察系統...
echo ===================================================
cd /d "%~dp0"
python main.py
if %errorlevel% neq 0 (
    echo.
    echo [錯誤] 啟動失敗！請檢查是否安裝了所有依賴套件。
    echo 您可以執行: pip install -r requirements.txt
    pause
)
