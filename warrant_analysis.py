"""
台股權證兩階段選股分析程式
基於「頂尖權證交易員」策略框架
資料來源：權證資料匯出 Excel（DataExport.xlsx）
"""

import pandas as pd
import numpy as np

# ── 設定 ──────────────────────────────────────────────────
INPUT_FILE = "20260527172302DataExport.xlsx"   # 改成你的檔名
OUTPUT_PHASE1 = "phase1_breakout.csv"
OUTPUT_PHASE2 = "phase2_momentum.csv"

# 排除 ETF / 指數型標的關鍵字
ETF_KEYWORDS = (
    "反|正2|00633|00637|00631|00655|00665|00664|00669|"
    "00680|00688|00693|00763|00738|00635|00708|00683|"
    "00885|00050|0050|00922|Y9999"
)

# ── 讀取資料 ──────────────────────────────────────────────
print("讀取資料中...")
df = pd.read_excel(INPUT_FILE)
df["日期"] = pd.to_datetime(df["日期"])
latest_date = df["日期"].max()
df = df[df["日期"] == latest_date].copy()
print(f"最新日期：{latest_date.date()}，共 {len(df)} 筆")

# ── 數值欄位轉型 ──────────────────────────────────────────
numeric_cols = [
    "DELTA", "剩餘期間(日)", "有效槓桿", "成本槓桿",
    "當日成交量", "溢價比率%", "隱含波動", "歷史波動性",
    "標的證券ROI%", "THETA", "VEGA", "未履約數", "流通在外比例(%)",
]
for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# ── 衍生指標 ──────────────────────────────────────────────
# IV/HV 比：> 1.3 代表造市商可能惡意調高 IV，應迴避
df["IV_HV_ratio"] = df["隱含波動"] / df["歷史波動性"]

# 只保留認購（含「購」字）
df = df[df["名稱"].str.contains("購", na=False)].copy()

# ── 共用過濾：排除 ETF / 指數型標的 ──────────────────────
is_pure_stock = ~df["標的證券"].str.contains(ETF_KEYWORDS, na=False)

# ═══════════════════════════════════════════════════════════
# 階段一：突破起漲 — 安全建倉
# ───────────────────────────────────────────────────────────
# 條件：
#   Delta       0.40 ~ 0.60  （價平附近，連動性佳）
#   剩餘天數    > 90 天       （降低 Theta 消耗，給整理空間）
#   IV/HV      0.70 ~ 1.30  （IV 合理，未被惡意調高）
#   當日成交量  >= 20 張      （造市流動性基本門檻）
#   現股今日漲幅 > 1.5%       （確認現股動能）
#   純個股      是
# ═══════════════════════════════════════════════════════════
print("\n【階段一】突破起漲 — 建倉條件篩選中...")

phase1_mask = (
    (df["DELTA"] >= 0.40) &
    (df["DELTA"] <= 0.60) &
    (df["剩餘期間(日)"] > 90) &
    (df["IV_HV_ratio"] >= 0.70) &
    (df["IV_HV_ratio"] <= 1.30) &
    (df["當日成交量"] >= 20) &
    (df["標的證券ROI%"] > 1.5) &
    is_pure_stock
)

phase1 = df[phase1_mask].copy()

# 排序：現股漲幅 > 成交量
phase1 = phase1.sort_values(
    ["標的證券ROI%", "當日成交量"],
    ascending=[False, False]
)

output_cols = [
    "代號", "名稱", "標的證券", "標的證券ROI%",
    "DELTA", "剩餘期間(日)", "有效槓桿", "成本槓桿",
    "隱含波動", "歷史波動性", "IV_HV_ratio",
    "溢價比率%", "當日成交量", "未履約數", "流通在外比例(%)",
    "THETA", "VEGA",
]

print(f"  符合條件：{len(phase1)} 筆")
print(phase1[output_cols].head(15).to_string(index=False))
phase1[output_cols].to_csv(OUTPUT_PHASE1, index=False, encoding="utf-8-sig")
print(f"  → 已儲存：{OUTPUT_PHASE1}")

# ═══════════════════════════════════════════════════════════
# 階段二：主升段飆漲 — 極致動能加碼
# ───────────────────────────────────────────────────────────
# 條件：
#   Delta       0.05 ~ 0.30  （價外 10-20%，利用 Gamma 加速）
#   剩餘天數    60 ~ 120 天   （承受 Theta 換取高槓桿）
#   有效槓桿    >= 5 倍       （實質槓桿門檻）
#   IV/HV      <= 1.30       （排除劣質造市商）
#   當日成交量  >= 10 張      （基本流動性）
#   現股今日漲幅 > 2.0%       （確認主升段動能）
#   純個股      是
# ═══════════════════════════════════════════════════════════
print("\n【階段二】主升段飆漲 — 動能加碼條件篩選中...")

phase2_mask = (
    (df["DELTA"] >= 0.05) &
    (df["DELTA"] <= 0.30) &
    (df["剩餘期間(日)"] >= 60) &
    (df["剩餘期間(日)"] <= 120) &
    (df["有效槓桿"] >= 5.0) &
    (df["IV_HV_ratio"] <= 1.30) &
    (df["當日成交量"] >= 10) &
    (df["標的證券ROI%"] > 2.0) &
    is_pure_stock
)

phase2 = df[phase2_mask].copy()

# 排序：有效槓桿（高到低）> 現股漲幅
phase2 = phase2.sort_values(
    ["有效槓桿", "標的證券ROI%"],
    ascending=[False, False]
)

print(f"  符合條件：{len(phase2)} 筆")
print(phase2[output_cols].head(15).to_string(index=False))
phase2[output_cols].to_csv(OUTPUT_PHASE2, index=False, encoding="utf-8-sig")
print(f"  → 已儲存：{OUTPUT_PHASE2}")

# ── 警示：IV 異常標的 ─────────────────────────────────────
print("\n【警示】IV/HV > 1.5 的高風險標的（造市商可能惡意調高 IV）：")
warn = df[
    (df["IV_HV_ratio"] > 1.5) &
    (df["當日成交量"] >= 10) &
    (df["標的證券ROI%"] > 2.0) &
    is_pure_stock
][["代號", "名稱", "標的證券", "IV_HV_ratio", "有效槓桿", "當日成交量"]].sort_values(
    "IV_HV_ratio", ascending=False
)
print(warn.head(10).to_string(index=False))

print("\n✅ 分析完成。")
print(f"   階段一結果 → {OUTPUT_PHASE1}")
print(f"   階段二結果 → {OUTPUT_PHASE2}")
