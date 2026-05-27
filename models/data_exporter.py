"""
資料匯出器模組
負責將篩選結果匯出為 CSV 或多分頁 Excel 檔案
"""

import pandas as pd
from pathlib import Path
from datetime import datetime


class DataExporter:
    """
    負責將篩選結果匯出為 CSV 或 Excel 格式。
    遵循 SRP，僅負責檔案格式轉換與儲存。
    """

    def export_csv(self, df: pd.DataFrame, filepath: str) -> str:
        """
        匯出單一 DataFrame 為 CSV 檔案（UTF-8 BOM，Excel 可正確開啟中文）。

        Args:
            df: 要匯出的 DataFrame
            filepath: 目標檔案路徑

        Returns:
            實際儲存的檔案路徑字串
        """
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(filepath, index=False, encoding="utf-8-sig")
        return str(filepath)

    def export_excel(self, df_dict: dict[str, pd.DataFrame], filepath: str) -> str:
        """
        將多個 DataFrame 匯出為多分頁 Excel 檔案，每個分頁對應一個篩選結果。

        Args:
            df_dict: {分頁名稱: DataFrame} 的字典，例如
                     {"階段一_建倉": df1, "階段二_加碼": df2, "IV_警示": df3}
            filepath: 目標 .xlsx 檔案路徑

        Returns:
            實際儲存的檔案路徑字串
        """
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
            for sheet_name, df in df_dict.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                # 美化：自動欄寬
                ws = writer.sheets[sheet_name]
                for col in ws.columns:
                    max_len = max(
                        (len(str(cell.value)) if cell.value else 0 for cell in col),
                        default=8,
                    )
                    ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 30)

        return str(filepath)

    @staticmethod
    def build_filepath(output_dir: str, prefix: str, ext: str) -> str:
        """
        依目前時間戳建立帶時間戳的輸出檔案路徑。

        Args:
            output_dir: 輸出目錄
            prefix: 檔名前綴，例如 "warrant_report"
            ext: 副檔名，例如 "csv" 或 "xlsx"

        Returns:
            完整檔案路徑字串
        """
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{ts}.{ext}"
        return str(Path(output_dir) / filename)
