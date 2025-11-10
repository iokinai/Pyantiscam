import torch
import whisper

from audio import Audio


class TranscriptorResult:
    def __init__(self, data: dict[str, str | list]):
        self.raw = data
        self.segments = data['segments']
        self.text = data['text']

class Transcriptor:
    def __init__(self):
        self.model = whisper.load_model("large")

    def transcribe(self, audio: Audio) -> TranscriptorResult:
        return TranscriptorResult(self.model.transcribe(audio.numpy(), fp16=False))

    def cleanup(self):
        del self.model
        torch.cuda.empty_cache()
