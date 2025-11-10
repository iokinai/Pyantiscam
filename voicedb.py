import os
import pickle

import torch
from torch.nn.functional import cosine_similarity


class VoiceDb:
    def __init__(self, path="voicedb/voices.pkl"):
        self.path = path
        try:
            with open(self.path, "rb") as f:
                self.voices = pickle.load(f)
        except OSError:
            os.mkdir("voicedb")
            self.voices = []
            self.dump()

        self.update_matrix()

    def dump(self):
        with open(self.path, "wb") as f:
            pickle.dump(self.voices, f)
        self.update_matrix()

    def update_matrix(self):
        if self.voices:
            self.voices_matrix = torch.stack(self.voices)
        else:
            self.voices_matrix = torch.empty((0, 0))

    def add_scammer(self, voice: torch.Tensor):
        self.voices.append(voice)
        self.dump()

    def find_voice(self, voice: torch.Tensor, threshold: float = 0.8) -> bool:
        if self.voices_matrix.numel() == 0:
            return False

        voice = voice.unsqueeze(0)

        sims = cosine_similarity(self.voices_matrix, voice, dim=1)

        return bool((sims >= threshold).any().item())
