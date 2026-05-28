# W-Insight (權證洞察) — 規格文件

## 專案概述

本系統將「頂尖權證交易員 skill」的選股策略框架實作為 PyQt6 桌面 GUI 應用程式，  
資料來源為 TEJ/平台匯出的 Excel 檔案（DataExport.xlsx），無需爬蟲。

---

## 1. 架構與選型

| 層次 | 技術 | 說明 |
|------|------|------|
| GUI | PyQt6 | 桌面應用框架 |
| 資料處理 | Pandas | Excel 讀取與篩選 |
| Excel 讀寫 | openpyxl | 匯出多分頁 Excel |
| PDF 生成 | reportlab | 報告書生成，含中文字型 |
| 圖片處理 | Pillow | 截圖格式轉換 |
| 測試 | pytest | 單元測試 |
| 架構模式 | MVC | Model/View/Controller 分離 |

```mermaid
graph TB
    subgraph "MVC 架構"
        M[Model 層] --> M1[DataLoader 資料載入]
        M --> M2[WarrantFilter 篩選邏輯]
        M --> M3[DataExporter CSV/Excel 匯出]
        M --> M4[ReportGenerator PDF 報告]
        M --> M5[TradingStrategy 策略文字]
        V[View 層] --> V1[MainWindow 主視窗]
        V --> V2[WarrantTable 資料表格]
        V --> V3[StockSearchBar 股票搜尋]
        V --> V4[ScreenshotPanel 截圖面板]
        C[Controller 層] --> C1[AppController 流程控制]
    end
    C1 -->|Qt Signal| V1
    V1 -->|事件| C1
    C1 --> M
```

---

## 2. 資料模型

```mermaid
erDiagram
    EXCEL_SOURCE {
        string file_path "Excel 檔案路徑"
        date data_date "資料日期（取最新）"
        int record_count "認購權證總筆數"
    }
    WARRANT_DATA {
        int code "代號"
        string name "名稱（含購字）"
        float delta "DELTA 0.05~0.60"
        float iv_hv_ratio "IV/HV比（衍生欄位）"
        int remaining_days "剩餘期間(日)"
        float effective_leverage "有效槓桿"
        float underlying_roi "標的證券ROI%"
        int daily_volume "當日成交量"
        string underlying_name "標的證券"
    }
    PDF_REPORT {
        image screenshot "封面日K截圖(可選)"
        table phase1 "階段一篩選結果"
        table phase2 "階段二篩選結果"
        table warnings "IV異常警示"
        text analysis "交易員策略解析"
        text exit_rules "出場紀律"
    }
    EXCEL_SOURCE ||--o{ WARRANT_DATA : "包含"
    WARRANT_DATA ||--o{ PDF_REPORT : "產出"
```

---

## 3. 關鍵流程

```mermaid
flowchart TD
    A[啟動 APP] --> B[載入 config.json]
    B --> C[自動讀取 Excel]
    C --> D[預處理: 轉型/IV_HV/認購/排除ETF]
    D --> E{使用者搜尋股票?}
    E -->|是| F[依標的名稱篩選]
    E -->|否| G[全量資料]
    F --> H[階段一篩選]
    G --> H
    H --> I[階段二篩選]
    I --> J[IV 異常偵測]
    J --> K[更新三個分頁表格]
    K --> L{操作}
    L -->|匯出 CSV/Excel| M[儲存結果檔案]
    L -->|匯出 PDF| N[生成含截圖的報告書]
    L -->|貼上截圖| O[載入日K截圖]
    L -->|重新整理| C
```

---

## 4. 兩階段策略篩選條件

### 階段一：突破起漲（安全建倉）

| 篩選條件 | 參數 | 說明 |
|----------|------|------|
| Delta | 0.40 ~ 0.60 | 價平附近，連動性佳 |
| 剩餘天數 | > 90 天 | 降低 Theta 時間損耗 |
| IV/HV | 0.70 ~ 1.30 | 避免造市商惡意調高 IV |
| 當日成交量 | ≥ 20 張 | 基本流動性門檻 |
| 標的 ROI% | > 1.5% | 確認現股動能 |

### 階段二：主升段飆漲（極致動能加碼）

| 篩選條件 | 參數 | 說明 |
|----------|------|------|
| Delta | 0.05 ~ 0.30 | 微價外，利用 Gamma 加速 |
| 剩餘天數 | 60 ~ 120 天 | 承受 Theta 換取高槓桿 |
| 有效槓桿 | ≥ 5 倍 | 實質槓桿門檻 |
| IV/HV | ≤ 1.30 | 排除劣質造市商 |
| 當日成交量 | ≥ 10 張 | 基本流動性 |
| 標的 ROI% | > 2.0% | 確認主升段動能 |

---

## 5. 模組關係圖

```mermaid
graph TB
    MW[MainWindow] --> AC[AppController]
    SSB[StockSearchBar] --> AC
    SP[ScreenshotPanel] --> AC
    AC --> DL[DataLoader]
    AC --> WF[WarrantFilter]
    AC --> EX[DataExporter]
    AC --> RG[ReportGenerator]
    AC --> TS[TradingStrategy]
    RG --> TS
    DL --> TW[WarrantTable]
    WF --> TW
```

---

## 6. 序列圖（主要流程）

```mermaid
sequenceDiagram
    actor User as 交易員
    participant MW as MainWindow
    participant AC as AppController
    participant DL as DataLoader
    participant WF as WarrantFilter
    participant RG as ReportGenerator

    User->>MW: 啟動 APP
    MW->>AC: load_and_analyze()
    AC->>DL: load_excel + preprocess
    DL-->>AC: DataFrame
    AC->>WF: filter_phase1 / filter_phase2 / detect_iv_warnings
    WF-->>AC: 三組結果
    AC-->>MW: Signal: phase1/2/warnings_updated
    MW->>MW: 更新三個分頁表格

    User->>MW: Ctrl+V 貼上截圖
    MW->>AC: set_screenshot(image)

    User->>MW: 點擊匯出 PDF
    MW->>AC: export_pdf(stock_name)
    AC->>RG: generate_report(...)
    RG-->>AC: PDF 路徑
    AC-->>MW: Signal: export_done
    MW->>User: 顯示完成對話框
```

---

## 7. 類別圖（核心類別）

```mermaid
classDiagram
    class AppController {
        +load_and_analyze(file_path)
        +search_stock(query)
        +set_screenshot(image)
        +export_csv(output_dir)
        +export_excel(output_dir)
        +export_pdf(stock_name, output_dir)
        -_run_filter()
    }
    class DataLoader {
        +load_excel(file_path) DataFrame
        +preprocess(df) DataFrame
    }
    class WarrantFilter {
        +filter_phase1(df, params) DataFrame
        +filter_phase2(df, params) DataFrame
        +detect_iv_warnings(df, threshold) DataFrame
        +search_by_stock(df, query) DataFrame
    }
    class TradingStrategy {
        +get_phase1_analysis() str
        +get_phase2_analysis() str
        +get_iv_risk_level(ratio) str
        +get_greek_tooltip(name) str
    }
    class ReportGenerator {
        +generate_report(...) str
        -_build_cover(...)
        -_build_phase_section(...)
        -_build_dataframe_table(df) Table
    }
    AppController --> DataLoader
    AppController --> WarrantFilter
    AppController --> ReportGenerator
    AppController --> TradingStrategy
    ReportGenerator --> TradingStrategy
```

---

## 8. 狀態圖

```mermaid
stateDiagram-v2
    [*] --> 初始化
    初始化 --> 載入中: 自動讀取 Excel
    載入中 --> 資料就緒: 成功
    載入中 --> 錯誤: 失敗
    錯誤 --> 載入中: 重新選擇
    資料就緒 --> 篩選顯示: 搜尋股票
    篩選顯示 --> 資料就緒: 清除搜尋
    資料就緒 --> 匯出中: 匯出
    篩選顯示 --> 匯出中: 匯出
    匯出中 --> 資料就緒: 完成
```

---

## 9. IV/HV 風險等級（ER 圖）

```mermaid
erDiagram
    IV_HV_LEVEL {
        string level "正常 / 注意 / 高風險"
        float threshold_min "下限"
        float threshold_max "上限"
        string color "顯示色彩"
        string action "建議行動"
    }
```

| 等級 | IV/HV 範圍 | 顏色 | 建議 |
|------|-----------|------|------|
| 正常 | 0.70 ~ 1.30 | 🟢 深藍 | 可安心交易 |
| 注意 | 1.30 ~ 1.50 | 🟡 橘色 | 注意觀察 |
| 高風險 | > 1.50 | 🔴 紅色 | 建議迴避 |

---

## 10. 出場紀律流程圖

```mermaid
flowchart LR
    subgraph "階段一出場"
        A1{跌破突破K棒低點?} -->|是| B1[立即停損出場]
        A2{權證虧損 ≥ 15%?} -->|是| B1
        A3{跌破10日線?} -->|是| B2[移動停利出場]
    end
    subgraph "階段二出場"
        C1{權證虧損 ≥ 20%?} -->|是| D1[嚴格停損出場]
        C2{跌破5日線?} -->|是| D2[獲利了結]
        C3{MACD縮小?} -->|是| D2
    end
```
