"""Groq Speech-to-Text への送信。

設計方針(要件より):
- whisper-large-v3-turbo のみ使用
- language=ja / response_format=text / temperature=0
- LLM後処理は一切しない（このクライアントは文字起こし結果をそのまま返す）

安定化ポイント:
- タイムアウトと 5xx は自動リトライ(指数バックオフ)
- HTTPステータスごとに原因が分かるメッセージ
- 送信前にファイルサイズを確認し、大きすぎる場合は事前に警告
"""

import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

# Free tier 25MB / Developer tier 100MB。安全側で 24MB を超えたら事前警告。
SIZE_WARN_BYTES = 24 * 1024 * 1024


class TranscriptionError(RuntimeError):
    """文字起こしに失敗（原因メッセージ付き）。"""


class GroqTranscriptionClient:
    def __init__(
        self,
        api_key: str,
        model: str = "whisper-large-v3-turbo",
        timeout: int = 60,
        max_retries: int = 2,
    ):
        if not api_key:
            raise ValueError("GROQ_API_KEY が未設定です")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.endpoint = "https://api.groq.com/openai/v1/audio/transcriptions"

    def transcribe(self, audio_path: str, language: str = "ja") -> str:
        size = os.path.getsize(audio_path)
        if size > SIZE_WARN_BYTES:
            logger.warning(
                "音声ファイルが大きいです (%.1fMB)。413エラーの可能性があります。",
                size / 1024 / 1024,
            )

        headers = {"Authorization": f"Bearer {self.api_key}"}
        data = {
            "model": self.model,
            "language": language,
            "response_format": "text",
            "temperature": "0",
        }

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                with open(audio_path, "rb") as audio_file:
                    files = {"file": ("audio.wav", audio_file, "audio/wav")}
                    response = requests.post(
                        self.endpoint,
                        headers=headers,
                        data=data,
                        files=files,
                        timeout=self.timeout,
                    )
            except requests.exceptions.Timeout as e:
                last_error = e
                logger.warning(
                    "タイムアウト (試行 %d/%d)", attempt + 1, self.max_retries + 1
                )
                self._sleep_backoff(attempt)
                continue
            except requests.exceptions.ConnectionError as e:
                raise TranscriptionError(
                    "ネットワークに接続できません。Wi-Fi/有線接続を確認してください。"
                ) from e

            # --- ステータス別のハンドリング ---
            if response.status_code == 401:
                raise TranscriptionError(
                    "401 Unauthorized: GROQ_API_KEY が正しくありません。Groq Console で再確認してください。"
                )
            if response.status_code == 413:
                raise TranscriptionError(
                    "413 Payload Too Large: 音声が大きすぎます。録音時間を短くしてください。"
                )
            if response.status_code == 429:
                raise TranscriptionError(
                    "429 Rate Limit: 短時間に使いすぎています。少し待ってから再実行してください。"
                )
            if response.status_code >= 500:
                last_error = TranscriptionError(
                    f"{response.status_code}: Groq側で一時的な問題が発生している可能性があります。"
                )
                logger.warning(
                    "サーバーエラー %d (試行 %d/%d)",
                    response.status_code,
                    attempt + 1,
                    self.max_retries + 1,
                )
                self._sleep_backoff(attempt)
                continue
            if not response.ok:
                raise TranscriptionError(
                    f"Groq API エラー {response.status_code}: {response.text[:300]}"
                )

            return response.text.strip()

        # リトライを使い切った
        raise TranscriptionError(
            f"リトライしても文字起こしに失敗しました: {last_error}"
        )

    @staticmethod
    def _sleep_backoff(attempt: int) -> None:
        # 0.8s, 1.6s, 3.2s ... の指数バックオフ
        time.sleep(0.8 * (2 ** attempt))
