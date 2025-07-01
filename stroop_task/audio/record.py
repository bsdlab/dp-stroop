# For the classical Stroop task, audio is recorded but transfered to a neutral
# voice on the fly. The natural voice is not stored for privacy reasons.
#
# Complex approaches do exist:
# -https://arxiv.org/pdf/2210.07002
# https://github.com/DigitalPhonetics/speaker-anonymization
#
# For us, more simple approaches are sufficient, as we do not aim to reconstruct
# words of a large memory, but simply distinguish 4 color words. This allows a
# high level of obfuscation -> this is realized by a narrow band filter
#
# https://alicecohenh.github.io/paperMLSP.pdf
#
# -> we use a bandpass filter an then just use a 4 level envelop to remove all
#    personal specific content

import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sounddevice as sd
import yaml
from faster_whisper import WhisperModel
from scipy import signal

from stroop_task.utils.logging import logger


def recording_to_dataframe(rec16k: np.ndarray) -> pd.DataFrame:
    """Model was trained on 16k data -> use resampled"""

    model_size = "small"
    # model = WhisperModel(model_size, device="cpu", compute_type="int8")
    model = WhisperModel(model_size, device="cpu", compute_type="float32")

    segments, info = model.transcribe(
        rec16k.flatten(),
        beam_size=8,
        word_timestamps=True,
    )

    data = []
    for seg in segments:
        if seg is not None:
            for word in seg.words:
                data.append(
                    {
                        "word_start": word.start,
                        "word_end": word.end,
                        "word": word.word,
                        "seg_start": seg.start,
                        "seg_end": seg.end,
                        "seg_text": seg.text,
                        "seg_id": seg.id,
                        "seg_avg_logprod": seg.avg_logprob,
                        "seg_compression_ratio": seg.compression_ratio,
                        "seg_no_speech_prob": seg.no_speech_prob,
                        "seg_temp": seg.temperature,
                    }
                )
    df = pd.DataFrame(data)

    return df


def recording_to_rectified(
    recording: np.ndarray, n_levels: int = 20, fs: int = 16_000, dt_mean_s: float = 0.02
) -> np.ndarray:

    n_mean = int(dt_mean_s * fs)

    rec_abs_max = np.hstack(
        [
            np.abs(recording[i : i + n_mean]).max()
            for i in range(0, len(recording), n_mean)
        ]
    )

    # repeat to get rectified signal with same shape as old
    recording_rectified = np.repeat(rec_abs_max, n_mean)

    # assure that we have only n_levels (equally spaced)
    rscaled = (
        (
            (recording_rectified - recording_rectified.min())
            / (recording_rectified.max() - recording_rectified.min())
        )
        * n_levels
    ).astype(
        int  # here we reach the n_levels -> then scale back
    )
    # plt.plot(recording)
    # plt.plot(recording_rectified)
    # plt.plot(rscaled)
    # plt.show()

    return rscaled


class SpokenStroopRecorder:

    def __init__(self):
        self.cfg = yaml.safe_load(open("./configs/audio.yaml", "r"))
        self.fs = self.cfg["device"]["sfreq"]
        self.rectified_recording: np.ndarray = np.empty(1)
        self.df: pd.DataFrame = pd.DataFrame()
        self.transformed: bool = False

    def record_for_s(self, duration_s: float):
        self.rec = sd.rec(int(duration_s * self.fs), samplerate=self.fs, channels=1)

    def transform(self):
        self.rec16k = signal.resample(
            self.rec.flatten(), num=int((len(self.rec) / self.fs) * 16_000)
        )
        logger.info("Transforming audio to rectified and transcription...")
        self.rectified_recording = recording_to_rectified(self.rec)
        logger.info("Transcribing sequence...")
        self.df = recording_to_dataframe(self.rec16k)  # type: ignore
        logger.info("Done.")
        self.transformed = True

    def persist_accumulated(self):
        if not self.transformed:
            self.transform()

        logcfg = yaml.safe_load(open("./configs/logging.yaml", "r"))
        pfx = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        file_np = Path(logcfg["log_file"]).parent.joinpath(f"{pfx}_audio.npy")
        file_pd = Path(logcfg["log_file"]).parent.joinpath(f"{pfx}_audio.tsv")

        logger.info(f"Persisting rectified to {file_np}")
        np.save(file_np, self.rectified_recording)
        logger.info(f"Persisting transcription to {file_pd}")
        self.df.to_csv(
            file_pd, sep="\t"
        )  # choosing tab separated as this is standard in BIDS


if __name__ == "__main__":
    duration = 5
    cfg = yaml.safe_load(open("./configs/audio.yaml", "r"))
    fs = cfg["device"]["sfreq"]

    # test recording
    sd.default.device = "MacBook Pro Microphone"
    rec = sd.rec(int(duration * fs), samplerate=fs, channels=1)
    sd.wait()
    print("done")
    rec16k = signal.resample(rec.flatten(), num=int((len(rec) / fs) * 16_000))

    sd.default.device = "MacBook Pro Speakers"
    sd.play(rec * 20)
