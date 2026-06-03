# W-Insight (權證洞察)

> 基於「頂尖權證交易員」策略框架的桌面 GUI 分析工具

## 功能特色

- 📊 **兩階段選股**：突破起漲建倉（Delta 0.4~0.6）、主升段加碼（高 Gamma 微價外）
- ⚠️ **IV 異常警示**：自動標記 IV/HV > 1.5 的高風險造市商標的（紅/黃/綠三色）
- 🔍 **股票搜尋**：即時輸入標的名稱，自動補全 + 智慧篩選（打字時補全選單零延遲跳出；僅在按下 Enter 鍵、點選下拉補全或將文字清空時，才觸發核心篩選與雙版預覽 PDF 生成，徹底杜絕打字卡頓，享受微秒級極速反應）
- 📷 **日K截圖**：支援 Ctrl+V 剪貼簿貼上、拖放、選擇圖片檔案
- 📄 **PDF 報告書**：封面含日K截圖，附交易員策略解析與出場紀律；頂部摘要卡片之「現股股價」與「日均價 DATA」最新 Excel 智慧同步（本機優先與網路降級機制），確保原版與 V2.0 股價完全一致且極致精準；新增「🎯 符合條件之權證綜合大評比與排名整理表」，打通 V1/V2 交叉名次，結合隱含波動率、天期實質槓桿與庫存/流通造市流動性代理指標；**重構 PDF 中的推薦權證卡片為 6 行版面，最前端新加上「價內外程度」、「履約價/標的價」、「剩餘期間」、「隱含波動率」、「歷史波動性」5 個實戰核心指標**，並設計極致金融級排版與物理防溢出。當點擊匯出時，系統會同時生成原版與 V2.0 版兩份獨立的 PDF 報告書檔案；**新增「一鍵批次匯出 PDF 報告」功能，系統會自動定位您指定的批次股票名單資料夾中最新的 Excel 名單檔案，並自動在您指定的預設 PDF 存放目錄下，創建一個以當日日期命名的資料夾（如 `20260529`），將所有雙版本 PDF 全自動輸出分類儲存，並支援 QProgressDialog 零凍結絲滑進度與取消功能，一鍵直達看盤整理極致乾淨！**
- 📋 **CSV/Excel 匯出**：UTF-8 BOM 編碼，三組篩選結果分頁輸出
- 📁 **路徑設定與持久化**：支援在最上方工具列的「📂 Excel 檔案路徑設定」區塊中，點擊「權證每日交易EXCEL資料夾:」按鈕隨時變更 Excel 路徑，且自動持久化存檔，下次啟動自動讀取
- 🌙 **深色金融主題**：專業深藍色 UI，希臘字母欄位 Tooltip 說明；左側邊欄新增 V1.0 (V0) 與 V2.0 評價權證標準的條列說明欄位；排名大表單（Table）全新加裝實時自主精算之「價內外程度」欄位（置於 名稱 後方），且欄位順序完全對齊實戰 Excel 檢視規格，並將「隱含波動」與「歷史波動性」全面升級為百分比格式呈現（如 58.58%），完美展現微小數據差距，供交易員隨時對照與檢索。

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
    "excel_path": "20260527172302DataExport.xlsx",
    "folder_unadjusted_price": "C:\\TejPro\\TejPro\\DataExport\\未調整股價(日)",
    "folder_daily_price": "C:\\TejPro\\TejPro\\DataExport\\日均價DATA"
}
```

> 「未調整股價(日)」為收盤價與漲跌幅的第一優先來源（G 欄「收盤價(元)」、J 欄「報酬率％」），「日均價DATA」為第二優先 Fallback。

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

## n8n 自動化與 API 啟動服務

本專案提供輕量級的 API 啟動服務與 n8n 工作流，支援定時自動啟動 W-Insight。

### 1. 運行 API 伺服器

API 伺服器僅使用 Python 標準庫，無任何額外依賴：

```powershell
python api_server.py
```

* **啟動 API**：`GET` 或 `POST` 呼叫 `http://localhost:8000/api/start` 即可異步開啟 W-Insight GUI 桌面應用。
* **狀態 API**：`GET` 呼叫 `http://localhost:8000/api/status` 可確認服務健康狀況。

### 2. 導入 n8n 工作流

我們已為您準備好工作流 JSON：[w-insight-n8n-workflow.json](w-insight-n8n-workflow.json)。

* **導入步驟**：
  1. 開啟您的 n8n 面板。
  2. 建立一個全新工作流，或進入現有工作流。
  3. 點選右上角的選單，選擇 **"Import from File"**，並選取 `w-insight-n8n-workflow.json`。
  4. 或是直接複製該檔案內容，並在 n8n 編輯區塊按下 `Ctrl+V` 貼上，即可一鍵導入。
* **觸發排程**：
  * 定時於每週一至五早上 9:00 自動向本機 API `http://localhost:8000/api/start` 發送 POST 請求，觸發 W-Insight APP 啟動。


