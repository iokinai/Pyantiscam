# Pyantiscam

ДЗ 2 для хакатона 2025 AI SHIELD
Команда: CSITeam

### Зависимости
Список зависимостей представлен в файле requirenments.txt

### Переменные окружения
Для запуска требуется установить 2 переменные окружения (в том числе это возможно в .env файле):
- `HF_TOKEN` - Hugging Face токен. Для корректной работы требуется доступ к следующим моделям:
  - pyannote/speaker-diarization-community-1
  - pyannote/embedding
- `OLLAMA_API_URL` - URL к Ollama (без пути, например: `http://localhost:11434`)
- `OLLAMA_MODEL` - модель Ollama (наприме: `ilyagusev/saiga_llama3`)

### Запуск
Для запуска нужно просто исполнить main.py:
`python main.py [audio_file]`
- Если путь к `audio_file` передан (например: `python main.py ~/audio.mp3`), обработан будет переданный файл
- Если пусть к `audio_file` не передан, но путь прописан в main.py в константе `AUDIO_FILE`, то будет использоваться он
- Иначе будет выброшено исключение
