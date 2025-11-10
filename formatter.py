from transcriptor import TranscriptorResult


def format_dialogue(diarization, transcription: TranscriptorResult) -> list:
    dialogue = []
    used_segments = set()

    for turn, speaker in diarization.speaker_diarization:
        texts_in_turn = []
        for segment in transcription.segments:
            if segment["end"] > turn.start and segment["start"] < turn.end: # type: ignore
                seg_text = segment["text"].strip() # type: ignore
                if seg_text not in used_segments:
                    texts_in_turn.append(seg_text)
                    used_segments.add(seg_text)

        if texts_in_turn:
            dialogue.append(f"{speaker} [{turn.start}, {turn.end}]: {' '.join(texts_in_turn)}")

    return dialogue
