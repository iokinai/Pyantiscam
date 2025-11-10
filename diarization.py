import torch
from pyannote.audio import Pipeline

from audio import Audio


class Diarization:
    def __init__(self, model: str, tk: str):
        pipeline = Pipeline.from_pretrained(
            model,
            token=tk,
            revision="main",
        )

        if pipeline is None:
            raise RuntimeError("Could not initialize the pipeline")

        self.pipeline = pipeline

    def diarize(self, audio: Audio):
        return self.pipeline(audio())

    def cleanup(self):
        del self.pipeline
        torch.cuda.empty_cache()
