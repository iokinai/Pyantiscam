import logging
import os
import queue
import threading
import uuid
from enum import Enum

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Form, UploadFile
from fastapi.exceptions import HTTPException

from audio import Audio
from run import AnalyzerEnvironment
from voicedb import VoiceDb

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

completed, completed_lock = {}, threading.Lock()

tasks = queue.Queue()
app = FastAPI()

class TaskType(Enum):
    Analyze = 0
    Transcript = 1
    Diarize = 2

class Task:
    def __init__(self, path: str, id: str, type: TaskType):
        self.path = path
        self.id = id
        self.type = type


def parse_task_type(type: str):
    match type:
        case "analyze":
            return TaskType.Analyze
        case "transcript":
            return TaskType.Transcript
        case "diarize":
            return TaskType.Diarize


def work():
    load_dotenv()

    ollama_api = os.getenv("OLLAMA_API_URL")
    ollama_model = os.getenv("OLLAMA_MODEL")
    tk = os.getenv("HF_TOKEN")

    if tk is None:
        raise RuntimeError("HF_TOKEN not set")

    env = AnalyzerEnvironment(
        "pyannote/speaker-diarization-community-1",
        "pyannote/embedding",
        VoiceDb(),
        tk
    )

    call_number = 1

    while True:
        task: Task = tasks.get()

        audio = Audio(task.path)

        if task.type == TaskType.Analyze:
            data = env.analyze_from_zero(audio, call_number, ollama_api, ollama_model)
            call_number += 1

        elif task.type == TaskType.Transcript:
            data = {}
            result = env.transcript(audio)

            data["text"] = result.text
            data["segments"] = []

            for seg in result.segments:
                data["segments"].append({
                    "start": seg["start"], # type: ignore
                    "end": seg["end"], # type: ignore
                    "text": seg["text"] # type: ignore
                })

        else:  # TaskType.Diarize
            result = env.diarize(audio)

            diarization_result = []
            for segment, _, speaker in result.speaker_diarization.itertracks(yield_label=True):
                diarization_result.append({
                    "start": segment.start,
                    "end": segment.end,
                    "speaker": speaker
                })

            data = diarization_result

        with completed_lock:
            completed[task.id] = data



@app.post("/schedule")
async def analyze(file: UploadFile, type: str = Form(...)):
    file_path = f"/tmp/{file.filename}"
    with open(file_path, "wb") as f:
        f.write(await file.read())

    task_type = parse_task_type(type)

    if task_type is None:
        raise HTTPException(status_code=400, detail="wrong task type")

    task_id = uuid.uuid4()
    tasks.put(Task(file_path, str(task_id), task_type))

    return {"task_id": task_id}

@app.get("/get_result")
async def get_result(id: str):
    ready, result = False, None

    try:
        with completed_lock:
            result = completed[id]
            ready = True
    except KeyError:
        pass

    return { "ready": ready, "result": result }

def main():
    load_dotenv()

    threading.Thread(target=work, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
