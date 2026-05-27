"""
設定管理器模組
負責讀寫 config.json 設定檔，提供預設值保護與型態安全存取。
"""

import json
from pathlib import Path


class ConfigManager:
    """
    管理 APP 設定的讀取、寫入與存取。
    遵循 SRP，僅負責設定持久化邏輯。
    """

    # 預設設定值（作為 config.json 不存在時的保護）
    DEFAULTS = {
        "excel_path": "20260527172302DataExport.xlsx",
        "output_dir": ".",
        "phase1_params": {
            "delta_min": 0.40,
            "delta_max": 0.60,
            "remaining_days_min": 90,
            "iv_hv_min": 0.70,
            "iv_hv_max": 1.30,
            "min_volume": 20,
            "min_underlying_roi": 1.5,
        },
        "phase2_params": {
            "delta_min": 0.05,
            "delta_max": 0.30,
            "remaining_days_min": 60,
            "remaining_days_max": 120,
            "min_leverage": 5.0,
            "iv_hv_max": 1.30,
            "min_volume": 10,
            "min_underlying_roi": 2.0,
        },
        "iv_warning_threshold": 1.5,
    }

    def __init__(self, config_path: str = "config.json"):
        """
        Args:
            config_path: config.json 的路徑，預設為程式執行目錄下的 config.json
        """
        self._config_path = Path(config_path)
        self._config = self.load()

    def load(self) -> dict:
        """
        從 JSON 檔案載入設定，若檔案不存在則使用預設值並自動建立檔案。

        Returns:
            合併預設值後的設定字典
        """
        config = dict(self.DEFAULTS)
        if self._config_path.exists():
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                # 深層合併，確保新增的預設鍵不會被舊設定檔遺漏
                config.update(loaded)
            except (json.JSONDecodeError, IOError):
                pass  # 設定檔損壞時使用預設值
        else:
            self.save(config)
        return config

    def save(self, config: dict | None = None) -> None:
        """
        將設定寫入 JSON 檔案。

        Args:
            config: 要儲存的設定字典，None 時儲存目前的設定
        """
        if config is not None:
            self._config = config
        try:
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, indent=4)
        except IOError:
            pass

    # ── 存取器 ─────────────────────────────────────────────

    def get_excel_path(self) -> str:
        """回傳 Excel 資料檔案路徑"""
        return self._config.get("excel_path", self.DEFAULTS["excel_path"])

    def set_excel_path(self, path: str) -> None:
        """更新 Excel 資料檔案路徑並自動儲存設定"""
        self._config["excel_path"] = path
        self.save()

    def get_output_dir(self) -> str:
        """回傳匯出檔案的輸出目錄"""
        return self._config.get("output_dir", self.DEFAULTS["output_dir"])

    def set_output_dir(self, path: str) -> None:
        """更新輸出目錄並自動儲存設定"""
        self._config["output_dir"] = path
        self.save()

    def get_phase1_params(self) -> dict:
        """回傳階段一篩選參數字典"""
        return self._config.get("phase1_params", self.DEFAULTS["phase1_params"])

    def get_phase2_params(self) -> dict:
        """回傳階段二篩選參數字典"""
        return self._config.get("phase2_params", self.DEFAULTS["phase2_params"])

    def get_iv_warning_threshold(self) -> float:
        """回傳 IV 異常警示的 IV/HV 門檻值"""
        return float(self._config.get("iv_warning_threshold", 1.5))
