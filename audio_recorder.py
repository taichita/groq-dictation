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

    def split_chunks(
        self,
        audio: np.ndarray,
        chunk_sec: float,
        search_sec: float = 4.0,
    ) -> list[np.ndarray]:
        """長い録音を、Groq の1リクエスト上限に収まる長さへ分割する。

        各境界の近くで最も音が静かな箇所（＝話の「間」）を選んで切るので、
        単語の途中で切れにくい。chunk_sec<=0 や十分短い場合は分割せず1個で返す。
        """
        if audio is None or audio.size == 0:
            return [audio]
        sr = self.sample_rate
        n = len(audio)
        chunk = int(chunk_sec * sr)
        if chunk <= 0 or n <= chunk:
            return [audio]

        win = max(1, int(0.1 * sr))            # 静けさ判定の窓: 100ms
        search = max(win, int(search_sec * sr))
        chunks: list[np.ndarray] = []
        start = 0
        while start < n:
            target = start + chunk
            if target >= n:
                chunks.append(audio[start:])
                break
            lo = max(start + chunk // 2, target - search)
            hi = min(n, target + search)
            split = self._quietest_index(audio, lo, hi, win)
            if split <= start:
                split = target            # 念のための前進保証（無限ループ防止）
            chunks.append(audio[start:split])
            start = split
        return chunks

    def _quietest_index(self, audio: np.ndarray, lo: int, hi: int, win: int) -> int:
        """[lo, hi) の中で最も静か（振幅が小さい）な窓の中心インデックスを返す。"""
        seg = np.abs(audio[lo:hi]).astype(np.float32).reshape(-1)
        if seg.size <= win:
            return (lo + hi) // 2
        csum = np.cumsum(seg)
        window_sums = csum[win:] - csum[:-win]   # 各位置から win サンプル分の振幅和
        idx = int(np.argmin(window_sums))        # 最も静かな窓の開始位置（seg内）
        return lo + idx + win // 2
