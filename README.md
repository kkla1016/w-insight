# W-Insight (權證洞察)

> 基於「頂尖權證交易員」策略框架的桌面 GUI 分析工具

## 功能特色

- 📊 **兩階段選股**：突破起漲建倉（Delta 0.4~0.6）、主升段加碼（高 Gamma 微價外）
- ⚠️ **IV 異常警示**：自動標記 IV/HV > 1.5 的高風險造市商標的（紅/黃/綠三色）
- 🔍 **股票搜尋**：即時輸入標的名稱，自動補全 + 智慧篩選（打字時補全選單零延遲跳出；僅在按下 Enter 鍵、點選下拉補全或將文字清空時，才觸發核心篩選與雙版預覽 PDF 生成，徹底杜絕打字卡頓，享受微秒級極速反應）
- 📷 **日K截圖**：支援 Ctrl+V 剪貼簿貼上、拖放、選擇圖片檔案
- 📄 **PDF 報告書**：封面含日K截圖，附交易員策略解析與出場紀律；頂部摘要卡片之「現股股價」與「日均價 DATA」最新 Excel 智慧同步（本機優先與網路降級機制），確保原版與 V2.0 股價完全一致且極致精準；新增「🎯 符合條件之權證綜合大評比與排名整理表」，打通 V1/V2 交叉名次，結合隱含波動率、天期實質槓桿與庫存/流通造市流動性代理指標，並支援極強的現股價格與履約價欄位容錯防禦性設計，為交易員提供最強實戰大評比與 100% 準確之價內外自主公式精算。當點擊匯出時，系統會同時生成原版與 V2.0 版兩份獨立的 PDF 報告書檔案，給予交易員最全面的決策資料。
- 📋 **CSV/Excel 匯出**：UTF-8 BOM 編碼，三組篩選結果分頁輸出
- 📁 **路徑設定與持久化**：支援在最上方工具列的「📂 Excel 檔案路徑設定」區塊中，點擊「權證每日交易EXCEL資料夾:」按鈕隨時變更 Excel 路徑，且自動持久化存檔，下次啟動自動讀取
- 🌙 **深色金融主題**：專業深藍色 UI，希臘字母欄位 Tooltip 說明

## 安裝需求

- Python 3.10+
- Windows 10/11（使用微軟正黑體渲染 PDF 中文）

```powershell
pip install -r requirements.txt
```

## 使用方式

```powershell
python main.py
```

## 資料來源

將 TEJ 或平台匯出的 `DataExport.xlsx` 放入專案目錄，  
或在 APP 工具列點選「📂 載入 Excel」指定路徑。

預設路徑設定於 `config.json`：

```json
{
    "excel_path": "20260527172302DataExport.xlsx"
}
```

## 專案結構

```
excel選權證/
├── main.py                   # 程式入口
├── config.json               # 設定檔（路徑與篩選參數）
├── requirements.txt
├── spec.md                   # 完整規格文件
├── models/
│   ├── data_loader.py        # Excel 讀取與預處理
│   ├── warrant_filter.py     # 兩階段篩選邏輯
│   ├── data_exporter.py      # CSV/Excel 匯出
│   ├── report_generator.py   # PDF 報告生成
│   └── trading_strategy.py   # 策略文字（Skill 整合）
├── views/
│   ├── main_window.py        # 主視窗
│   ├── warrant_table.py      # 資料表格元件
│   ├── stock_search_bar.py   # 股票搜尋列
│   └── screenshot_panel.py   # 截圖面板
├── controllers/
│   └── app_controller.py     # 應用控制器
├── utils/
│   └── config_manager.py     # 設定管理器
└── tests/                    # 單元測試（pytest）
```

## 快速鍵

| 按鍵 | 功能 |
|------|------|
| `Ctrl+V` | 從剪貼簿貼上日K截圖 |
| `F5` | 重新整理（重新讀取 Excel） |

## 執行單元測試

```powershell
python -m pytest tests/ -v
```

## 策略說明

詳見 [spec.md](spec.md) 與 `warrant-trader-expert` skill。

| 階段 | Delta | 天期 | 重點 |
|------|-------|------|------|
| 一：突破建倉 | 0.40~0.60 | >90天 | 價平長天期，防洗盤 |
| 二：主升加碼 | 0.05~0.30 | 60~120天 | 微價外，高 Gamma 爆發 |
