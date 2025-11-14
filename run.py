import json
import logging
import os

from dotenv import load_dotenv

import llm
from audio import Audio
from diarization import Diarization
from formatter import format_dialogue
from regex_filter import FilteringString, RegexFilter
from transcriptor import Transcriptor, TranscriptorResult
from voice import voices_to_dict
from voicedb import VoiceDb


def save_scam_voice(result, known, voices, vdb: VoiceDb):
    logging.debug(result)
    for speaker in result["scammers"]:
        if speaker not in known:
            vdb.add_scammer(voices[speaker])

def format_output(result):
    print(f"Описание звонка: {result["summary"]}")
    print(f"Тип звонка: {result["category"]}")
    print(f"Риск-скор: {result["risk_score"]}")

    if result["indicators"]:
        print("Индикаторы мощенничества: " + ", ".join(result["indicators"]))

    try:
        susp = result['suspiscious_segments']

        for moment in susp:
            print(moment)
    except KeyError:
        pass

def run(audio_env: str | None, audio_hardcoded: str | None):
    audio_path = None

    if audio_env is not None:
        audio_path = audio_env
    elif audio_hardcoded is not None:
        audio_path = audio_hardcoded
    else:
        raise RuntimeError("Audio path is not provided")

    output_results(audio_path)


class AnalyzerEnvironment:
    def __init__(self, diar_model: str, inter_model: str, voice_db: VoiceDb, hf_token: str):
        self.voice_db = voice_db
        self.transcriptor = Transcriptor()
        self.diarizator = Diarization(diar_model, hf_token)
        self.interference_model = inter_model
        self.hf_token = hf_token

    def transcript(self, audio: Audio):
        return self.transcriptor.transcribe(audio)

    def diarize(self, audio: Audio):
        return self.diarizator.diarize(audio)

    def dialogue(self, audio: Audio | None = None, transcription: TranscriptorResult | None = None, diarization = None):
        if audio is None and (transcription is None or diarization is None):
            raise RuntimeError("Audio or both transcription and diarization is not provided")

        if transcription is None:
            transcription = self.transcript(audio) # type: ignore

        if diarization is None:
            diarization = self.diarize(audio) # type: ignore

        return format_dialogue(diarization, transcription)

    def voice_embeddings(self, audio: Audio, diarization = None):
        if diarization is None:
            diarization = self.diarize(audio) # type: ignore

        return voices_to_dict(diarization, self.interference_model, self.hf_token, audio)

    def check_voice_database(self, voices):
        in_db = []

        for sp, voice in voices.items():
            if self.voice_db.find_voice(voice):
                logging.info(f"{sp}'s voice found in the voicedb")
                in_db.append(sp)

        return in_db

    def analyze(self, dialogue, call_number, in_db, ollama_api, ollama_model):
        return llm.analyze_with_llm(dialogue, call_number, in_db, ollama_api, ollama_model)

    def analyze_from_zero(self, audio: Audio, call_number: int, ollama_api, ollama_model):
        transcription = self.transcript(audio)
        diarization = self.diarize(audio)
        voice_embeddings = self.voice_embeddings(audio, diarization=diarization)
        dialogue = self.dialogue(transcription=transcription, diarization=diarization)
        in_db = self.check_voice_database(voice_embeddings)

        response = self.analyze(dialogue, call_number, in_db, ollama_api, ollama_model)

        r = FilteringString(response['response']).filter(RegexFilter.md_json()) # type: ignore

        #logging.debug(r)

        result = json.loads(str(r))
        #logging.debug(result)

        self.save_scammers(result, voice_embeddings, in_db)


        return result

    def save_scammers(self, data, voices, skip):
        save_scam_voice(data, skip, voices, self.voice_db)


def run_with_file(audio_file: str):
    load_dotenv()

    model = "pyannote/speaker-diarization-community-1"
    interference_model = "pyannote/embedding"
    tk = os.getenv("HF_TOKEN")

    if tk is None:
        raise RuntimeError("Could not get HF_TOKEN from env vars")

    vdb = VoiceDb()

    logging.info("Loading environment...")
    env = AnalyzerEnvironment(model, interference_model, vdb, tk)
    logging.info("Loaded environment")

    audio = Audio(audio_file)



    data = env.analyze_from_zero(audio, 1, os.getenv("OLLAMA_API_URL"), os.getenv("OLLAMA_MODEL"))

    # transc = Transcriptor()
    # logging.info("Loaded transcription model")
    # diariz = Diarization(model, tk)
    # logging.info("Loaded diarization model")

    # logging.info("Started transcripting...")
    # transcription = transc.transcribe(audio)
    # logging.info("Started diarization...")
    # diarization = diariz.diarize(audio)

    # logging.info("Formatting transcription and diarization into dialogue...")
    # dialogue = format_dialogue(diarization, transcription)

    # logging.info("Loading voice embeddings...")
    # speaker_embeddings = voices_to_dict(diarization, interference_model, tk, audio)

    # in_db = []

    # for sp, voice in speaker_embeddings.items():
    #     if vdb.find_voice(voice):
    #         logging.info(f"{sp}'s voice found in the voicedb")
    #         in_db.append(sp)

    # logging.info("Sending the request to LLM...")

    #response = llm.analyze_with_llm(dialogue, 1, in_db, os.getenv("OLLAMA_API_URL"), os.getenv("OLLAMA_MODEL"))
    # logging.info("Got response from LLM")
    # r = FilteringString(response['response']).filter(RegexFilter.md_json()) # type: ignore
    # logging.debug(r)

    # data = json.loads(str(r))
    # logging.debug(data)

    #save_scam_voice(data, in_db, speaker_embeddings, vdb)

    return data

def output_results(audio_file: str):
    try:
        result = run_with_file(audio_file)

        print("\n\n")
        print("=================РЕЗУЛЬТАТ=================")
        format_output(result)
    except Exception as e:
        print(f"Произошла ошибка: {e}")
