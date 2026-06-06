"""ローカル置換辞書による単純文字列置換。

重要(要件より): ここでLLMや文脈推定は一切しない。
replacement.json の キー→値 を順に str.replace するだけ。
誤変換の修正はすべてこの辞書で行う。
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ReplacementEngine:
    def __init__(self, replacement_file: Path):
        self.replacement_file = Path(replacement_file)
        self.rules: dict[str, str] = self._load_rules()

    def _load_rules(self) -> dict[str, str]:
        if not self.replacement_file.exists():
            logger.warning(
                "置換辞書が見つかりません: %s (置換なしで続行します)",
                self.replacement_file,
            )
            return {}
        try:
            with self.replacement_file.open("r", encoding="utf-8") as f:
                rules = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(
                "置換辞書 %s の JSON が壊れています (置換なしで続行します): %s",
                self.replacement_file,
                e,
            )
            return {}
        if not isinstance(rules, dict):
            logger.error("置換辞書はオブジェクト({...})にしてください。置換なしで続行します。")
            return {}
        logger.info("置換辞書を読み込みました (%d 件)", len(rules))
        return {str(k): str(v) for k, v in rules.items()}

    def apply(self, text: str) -> str:
        result = text
        for source, target in self.rules.items():
            if source:
                result = result.replace(source, target)
        return result
