import torch
import torchaudio
from pyannote.audio import Inference, Model
from pyannote.core import SlidingWindowFeature


def voices_to_dict(diarization, model: str, tk: str, audio):
    m = Model.from_pretrained(model, token=tk)
    if m is None:
        raise RuntimeError(f"Could not initialized model: {model}")

    embedding_model = Inference(m)

    speaker_embeddings = {}
    sr = 16000

    waveform = torchaudio.functional.resample(audio.waveform, audio.sr, sr)

    for turn, speaker in diarization.speaker_diarization:
        start_sample = int(turn.start * sr)
        end_sample   = int(turn.end   * sr)
        turn_waveform = waveform[:, start_sample:end_sample]

        if turn_waveform.shape[1] < sr * 0.2:
            continue

        emb = embedding_model({"waveform": turn_waveform, "sample_rate": sr})

        if isinstance(emb, SlidingWindowFeature):
            emb_tensor = torch.from_numpy(emb.data)
            emb_tensor = emb_tensor.mean(dim=0)
        else:
            emb_tensor = emb

        if speaker not in speaker_embeddings:
            speaker_embeddings[speaker] = []
        speaker_embeddings[speaker].append(emb_tensor)

    for speaker in speaker_embeddings:
        speaker_embeddings[speaker] = torch.stack(speaker_embeddings[speaker]).mean(dim=0)

    return speaker_embeddings
