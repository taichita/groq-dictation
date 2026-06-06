"""マイク録音と wav 保存。

安定化ポイント:
- マイク権限がない/デバイスが無い場合に分かりやすい例外を投げる
- 録音の長さ(秒)を返し、空録音や短すぎる録音を呼び出し側で弾けるようにする
- コールバック内で例外を握りつぶさず、状態を記録しておく
"""

import logging

import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write

logger = logging.getLogger(__name__)


class MicPermissionError(RuntimeError):
    """マイクが開けない（権限なし/デバイス無し）。"""


class AudioRecorder:
    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self.frames: list[np.ndarray] = []
        self.stream = None
        self._overflow_warned = False

    def _callback(self, indata, frames, time_info, status):
        if status and not self._overflow_warned:
            # オーバーフロー等は一度だけ警告（ログを溢れさせない）
            logger.warning("録音ストリーム警告: %s", status)
            self._overflow_warned = True
        self.frames.append(indata.copy())

    def start(self) -> None:
        self.frames = []
        self._overflow_warned = False
        try:
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                callback=self._callback,
            )
            self.stream.start()
        except sd.PortAudioError as e:
            self.stream = None
            raise MicPermissionError(
                "マイクを開けませんでした。macOSの「システム設定 > プライバシーとセキュリティ > "
                "マイク」で、このアプリを実行しているターミナル(またはiTerm等)を許可してください。"
                f" 詳細: {e}"
            ) from e

    def stop(self) -> tuple[np.ndarray, float]:
        """録音を停止し、(音声データ, 秒数) を返す。"""
        if self.stream is None:
            return np.array([], dtype=np.float32), 0.0
        try:
            self.stream.stop()
            self.stream.close()
        finally:
            self.stream = None

        if not self.frames:
            return np.array([], dtype=np.float32), 0.0

        audio = np.concatenate(self.frames, axis=0)
        duration = len(audio) / float(self.sample_rate)
        return audio, duration

    def save_wav(self, path: str, audio_data: np.ndarray) -> None:
        if audio_data.size == 0:
            raise ValueError("録音データが空です。")
        audio_int16 = np.int16(np.clip(audio_data, -1.0, 1.0) * 32767)
        write(path, self.sample_rate, audio_int16)
