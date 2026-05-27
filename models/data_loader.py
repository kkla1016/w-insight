"""
資料載入器模組
負責讀取 Excel 匯出檔案並進行資料預處理
"""

import pandas as pd
import numpy as np
from pathlib import Path


class DataLoader:
    """
    負責讀取 DataExport.xlsx 並執行所有前置資料清洗工作。
    遵循單一責任原則（SRP），僅負責資料載入與預處理。
    """

    # 需要轉換為數值型態的欄位清單
    NUMERIC_COLS = [
        "DELTA", "GAMMA", "VEGA", "THETA", "RHO",
        "剩餘期間(日)", "有效槓桿", "成本槓桿",
        "當日成交量", "溢價比率%", "隱含波動", "歷史波動性",
        "標的證券ROI%", "未履約數", "流通在外比例(%)",
        "權證ROI(%)", "權證收盤價(元)", "履約價(元)",
        "標的證券價格(元)", "權證高估%",
    ]

    # 排除 ETF / 指數型標的的關鍵字正則表達式
    ETF_PATTERN = (
        r"反|正2|00633|00637|00631|00655|00665|00664|00669|"
        r"00680|00688|00693|00763|00738|00635|00708|00683|"
        r"00885|00050|0050|00922|Y9999"
    )

    def load_excel(self, file_path: str) -> pd.DataFrame:
        """
        讀取 Excel 檔案，僅保留最新日期的資料。

        Args:
            file_path: Excel 檔案的絕對或相對路徑

        Returns:
            僅包含最新日期資料的 DataFrame

        Raises:
            FileNotFoundError: 檔案不存在時
            ValueError: 資料格式不符時
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"找不到資料檔案：{file_path}")

        df = pd.read_excel(file_path, dtype={"代號": str})

        # 確認關鍵欄位存在
        required_cols = {"名稱", "標的證券", "DELTA", "剩餘期間(日)"}
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"Excel 缺少必要欄位：{missing}")

        # 處理日期欄位（支援字串或日期型態）
        if "日期" in df.columns:
            df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
            latest_date = df["日期"].max()
            df = df[df["日期"] == latest_date].copy()
            self._latest_date = latest_date
        else:
            self._latest_date = None

        return df

    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        對載入的原始資料執行完整的前置處理流程：
        數值轉型 → IV/HV 計算 → 篩選認購 → 排除 ETF

        Args:
            df: 原始 DataFrame

        Returns:
            清洗後可直接用於篩選的 DataFrame
        """
        df = self._convert_numeric(df)
        df = self._calculate_iv_hv(df)
        df = self._filter_call_warrants(df)
        df = self._exclude_etf(df)
        return df.reset_index(drop=True)

    @property
    def latest_date(self):
        """回傳最後讀取的資料日期"""
        return getattr(self, "_latest_date", None)

    def _convert_numeric(self, df: pd.DataFrame) -> pd.DataFrame:
        """將指定欄位強制轉換為數值型態，無法轉換的設為 NaN"""
        for col in self.NUMERIC_COLS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def _calculate_iv_hv(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        計算 IV/HV 比率（隱含波動 / 歷史波動性）。
        比率 > 1.3 代表造市商可能惡意調高 IV。
        """
        if "隱含波動" in df.columns and "歷史波動性" in df.columns:
            # 避免除以零，HV 為零時設為 NaN
            df["IV_HV_ratio"] = df["隱含波動"] / df["歷史波動性"].replace(0, np.nan)
        else:
            df["IV_HV_ratio"] = np.nan
        return df

    def _filter_call_warrants(self, df: pd.DataFrame) -> pd.DataFrame:
        """只保留認購權證（名稱含「購」字）"""
        if "名稱" in df.columns:
            return df[df["名稱"].str.contains("購", na=False)].copy()
        return df

    def _exclude_etf(self, df: pd.DataFrame) -> pd.DataFrame:
        """排除 ETF 及指數型標的，只保留純個股權證"""
        if "標的證券" in df.columns:
            is_pure_stock = ~df["標的證券"].str.contains(
                self.ETF_PATTERN, na=False, regex=True
            )
            return df[is_pure_stock].copy()
        return df
