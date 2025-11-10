import json
import logging
import os
import re

from dotenv import load_dotenv

import llm
from audio import Audio
from diarization import Diarization
from formatter import format_dialogue
from transcriptor import Transcriptor
from voice import voices_to_dict
from voicedb import VoiceDb


def save_scam_voice(result, known, voices, vdb: VoiceDb):
    for speaker in result["scammers"]:
        if speaker not in known:
            vdb.add_scammer(voices[speaker])

def format_output(result):
    print(f"Описание звонка: {result["summary"]}")
    print(f"Тип звонка: {result["category"]}")
    print(f"Риск-скор: {result["risk_score"]}")

    if result["indicators"]:
        print("Индикаторы мощенничества: " + ", ".join(result["indicators"]))

def run(audio_env: str | None, audio_hardcoded: str | None):
    audio_path = None

    if audio_env is not None:
        audio_path = audio_env
    elif audio_hardcoded is not None:
        audio_path = audio_hardcoded
    else:
        raise RuntimeError("Audio path is not provided")

    run_with_file(audio_path)


def run_with_file(audio_file: str):
    load_dotenv()

    model = "pyannote/speaker-diarization-community-1"
    interference_model = "pyannote/embedding"
    tk = os.getenv("HF_TOKEN")

    if tk is None:
        raise RuntimeError("Could not get HF_TOKEN from env vars")

    vdb = VoiceDb()

    audio = Audio(audio_file)
    transc = Transcriptor()
    logging.info("Loaded transcription model")
    diariz = Diarization(model, tk)
    logging.info("Loaded diarization model")

    logging.info("Started transcripting...")
    transcription = transc.transcribe(audio)
    logging.info("Started diarization...")
    diarization = diariz.diarize(audio)

    logging.info("Formatting transcription and diarization into dialogue...")
    dialogue = format_dialogue(diarization, transcription)

    logging.info("Loading voice embeddings...")
    speaker_embeddings = voices_to_dict(diarization, interference_model, tk, audio)

    in_db = []

    for sp, voice in speaker_embeddings.items():
        if vdb.find_voice(voice):
            logging.info(f"{sp}'s voice found in the voicedb")
            in_db.append(sp)

    prompt = llm.generate_prompt(dialogue, 1, in_db)

    logging.info("Sending the request to LLM...")
    response = llm.send_request(prompt, os.getenv("OLLAMA_API_URL"), os.getenv("OLLAMA_MODEL"))
    logging.info("Got response from LLM")
    r = response['response'] # type: ignore
    logging.debug(r)

    cleaned = re.sub(r"```json\s*|\s*```", "", r, flags=re.IGNORECASE).strip()

    data = json.loads(cleaned)
    logging.debug(data)

    save_scam_voice(data, in_db, speaker_embeddings, vdb)

    print("\n\n")
    print("=================РЕЗУЛЬТАТ=================")

    format_output(data)
