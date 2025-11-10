import numpy as np
import torchaudio
from torch import Tensor


class Audio:
    def __init__(self, path: str):
        self.path = path
        self.target_sr = 44100
        self.waveform, self.sr = torchaudio.load(path)

    def requires_resample(self) -> bool:
        return self.sr == self.target_sr

    def numpy(self):
        mono_wf = self.waveform.mean(dim=0)
        sr = 16000
        inp = self.resample(mono_wf, sr).numpy().astype(np.float32)

        return inp

    def resample(self, input, target):
        resampler = torchaudio.transforms.Resample(orig_freq=self.sr, new_freq=target)
        return resampler(input)

    def __call__(self):
        if self.requires_resample():
            self.waveform = self.resample(self.waveform, self.target_sr)

        return {"waveform": self.waveform, "sample_rate": self.target_sr, "uri": "audio"}


class WaveformAudio:
    def __init__(self, waveform: Tensor, sr: int):
        self.waveform = waveform
        self.sr = sr

    def __call__(self):
        return {"waveform": self.waveform, "sample_rate": self.sr}
