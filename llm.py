import json
import logging

import requests

from regex_filter import FilteringString, RegexFilter

__LLM_INSTRUCTION ="""
Роль: Ты — AI-анализатор безопасности, специализирующийся на выявлении мошеннических и подозрительных паттернов в телефонных разговорах. Твоя задача — проанализировать предоставленный текст звонка и присвоить ему одну из трёх категорий: мошеннический, подозрительный или обычный.

Критерии классификации:

Мошеннический: Звонок содержит один или несколько ключевых индикаторов мошенничества:

Прямой запрос конфиденциальных данных: просьба сообщить код из SMS, пароль, данные карты, паспорта, CVC/CVV.

Попытка удалённого доступа: инструкции по установке приложений (AnyDesk, TeamViewer и т.д.), нажатию кнопок в меню телефона.

Финансовые требования: прямая или замаскированная просьба о переводе денег, оплате, пополнении счета.

Имитация официального лица: представился сотрудником банка, государственного органа (Почта России, ФОМС, ФСБ, МВД), службы безопасности, курьерской службы, техподдержки — в сочетании с одним из вышеуказанных индикаторов.

Сценарий "Друг/Родственник": абонент не представляется, но ведёт себя как знакомый и просит срочную финансовую помощь.

Подозрительный: Звонок вызывает настороженность, но не содержит явных мошеннических инструкций:

Звонящий представляется официальным лицом (банк, соцслужба), но цель звонка размыта или неестественна.

Используется давление (срочность, запугивание, излишняя настойчивость), но без прямых просьб о деньгах или кодах.

Есть несоответствия в легенде (например, абонент опровергает базовый предлог звонка).

Запрос общих персональных данных (ФИО, адрес) без явной необходимости.

Обычный: Звонок не содержит признаков мошенничества или подозрительной активности:

Деловое или личное общение без признаков обмана.

Информационные звонки (напоминания, опросы), где личные данные не запрашиваются или запрашиваются в рамках стандартной процедуры (например, для идентификации).

Четко идентифицируемый коммерческий или сервисный звонок без давления и запроса конфиденциальной информации.

risk_score - число от 0 до 10.
0 означает, что в звонке вообще нет признаков мошенничества.
10 означает, что звонок содержит неопровержимые признаки мошенничества.
Обязательно убедись, что риск-скор соответствует присвоенной категории:
- Если category == "fraudulent", risk_score должен быть >= 7
- Если category == "suspicious", risk_score обычно 3-6
- Если category == "normal", risk_score 0-2

segment_risk_score - число от 0 до 10.
0 — в этом сегменте нет признаков мошенничества, 10 — доказанный обман.
Если сегмент явно указывает на мошенничество, ставь ≥7.
Если нет явных признаков, ставь 0-3.
"""

def generate_regular_prompt(dialogue: list[str], call_number: int, ksv: list[str]):
    return __LLM_INSTRUCTION + """Инструкция:
    Проанализируй предоставленный ниже текст транскрипта телефонного звонка. Опирайся исключительно на текст. Присвой звонку одну из трёх категорий: МОШЕННИЧЕСКИЙ, ПОДОЗРИТЕЛЬНЫЙ или ОБЫЧНЫЙ.

    Формат входных данных:

    {
        // Диалог представляет собой массив фраз вида: SPEAKER_N [segment_start, segment_end]: text. Учитывай, что в номерах спикеров может быть ошибка, поэтому делай вывод в том числе исходя из контекста
        "dialogue": [string],
        // Номер звонка, просто число
        "call_number": number,
        // Если голос, похожий на голос одного или нескольких спикеров есть в базе данных известных нам мошенников, то они будут перечислены тут. Это НЕ 100% доказательство, но может добавлять вес. Пример: [SPEAKER_01, SPEAKER_00]
        "known_scammers_voice": [string]
    }

    Формат выходных данных:
    {
        // Номер звонка, тот же что и у запроса
        "call_number": number,
        // Категория звонка
        "category": "normal" | "suspicious" | "fraudulent",
        // Общее содержание звонка
        "summary": string,
        // Риск-скор от 0 до 10. 10 - значит что звонок 100% мошеннический, а 0 - что звонок 100% чистый
        "risk_score": number,
        // Индикаторы мошенничества / подозрительные моменты (если есть)
        "indicators": [string]
        // Спикеры, являющиеся мошенниками (например, [SPEAKER_00, SPEAKER_01])
        "scammers": [string]
    }
    ВАЖНО: Вывод строго соответствует схеме JSON. Никаких дополнительных полей, вложенных объектов, или советов давать нельзя. Так же нельзя переименовывать поля, переводить их на русский язык и так далее. Схема должна быть строго такой
    Выходные данные будут обрабатываться программой, поэтому любые отличия от этой схемы приведут к ошибке

    Входные данные:
    """ + json.dumps({
        "dialogue": dialogue,
        "call_number": call_number,
        "known_scammers_voice": ksv
    }, ensure_ascii=False)


def generate_segment_propmt(prev_summary: str | None, segment: list[str], segment_num: int, segment_count: int):
    s = __LLM_INSTRUCTION + """
    Поскольку звонок слишком большой, мы разбили его на сегменты
    Это сегмент {segment_num} из {segment_count}

    Твоя задача - сгенерировать короткое описание этого сегмента диалога. Учти, что твоя конечная цель - определить, является
    ли этот звонок мошенническим, поэтому имеет смысл добавлять в сводку только то, что может помочь при принятии этого решения

    Формат входных данных:

    {
        "prev_summary": string | null,
        "segment": [string]
    }

    prev_summary - это сводка предыдущих сегментов. Он может быть null если это первый сегмент, или в предыдущих нет ничего, на что стоит обратить внимание
    segment - это сам диалог - список строк формата: SPEAKER_N [segment_start, segment_end]: text. Учитывай, что в номерах спикеров может быть ошибка, поэтому делай вывод в том числе исходя из контекста

    Формат выходных данных:

    {
        "summary": string | null,
        "segment_risk_score": number,
        "scammers": [string]
    }

    summary - это объединенная сводка этого сегмента и предыдущих. Это строка, или null (если ничего важного нет ни в этом сегменте, ни в предыдущих), но учитывай, что она
    не должна быть слишком большой. Стоит добавлять туда только самое важное, что поможет в принятии решения.

    segment_risk_score - риск-скор этого сегмента. Это число от 0 до 10, где 0 значит, что в этом сегменте вообще нет признаков социальной инженерии, а 10 - что этот сегмент содержит неопровержимые доказательства попытки обмана

    scammers - массив тех, кого ты подозреваешь в мошенничестве в этом сегменте (например, SPEAKER_00)

    !!! ВАЖНО !!!
    Ответь строго в формате JSON, без текста до или после.
    НЕ добавляй объяснения.
    НЕ добавляй рассуждения.
    НЕ добавляй вступления.
    Если формат нарушен — система завершит процесс.
    ТВОЙ ОТВЕТ ДОЛЖЕН БЫТЬ *ТОЛЬКО JSON*.


    Входные данные: {input_string}

    """
    s = s.replace("{segment_num}", str(segment_num))
    s = s.replace("{segment_count}", str(segment_count))
    s = s.replace("{input_string}", json.dumps({
        "prev_summary": prev_summary,
        "segment": segment
    }, ensure_ascii=False))

    return s

def generate_final_segment_propmt(prev_summary: str | None, segment: list[str], call_number: int, ksv: list[str], prev_risc_scores: list[int], prev_scammers: list[str]):
    s = __LLM_INSTRUCTION + """

    Поскольку звонок слишком большой, мы разбили его на сегменты
    Это последний сегмент, и тут тебе нужно принять решение, является ли звонок мошенническим

    Формат входных данных:

    {
        "call_number": number
        "prev_summary": string | null,
        "segment": [string],
        "known_scammers_voice": [string],
        "prev_risk_scores": [number],
        "prev_scammers": [string]
    }

    call_number - номер звонка

    prev_summary - краткое описание предыдущих сегментов, где наибольшее внимание уделено признакам мошенничества. Если признаков мошенничества не было ни в одном из предыдущих сегментов - null

    segment - это сам диалог - список строк формата: SPEAKER_N [segment_start, segment_end]: text. Учитывай, что в номерах спикеров может быть ошибка, поэтому делай вывод в том числе исходя из контекста

    known_scammers_voice - если голос, похожий на голос одного или нескольких спикеров есть в базе данных известных нам мошенников, то они будут перечислены тут. Это НЕ 100% доказательство, но может добавлять вес. Пример: [SPEAKER_01, SPEAKER_00]

    prev_risk_scores - массив с риск-скорами предыдущих сегментов. Риск-скор - это число от 0 до 10, где 0 значит, что в этом сегменте вообще нет признаков социальной инженерии, а 10 - что этот сегмент содержит неопровержимые доказательства попытки обмана.
    Наибольшее внимание стоит обращать на сегменты, где риск-скор высокий, поскольку в сегментах, где он низкий, говорящие могли просто здороваться, или обсужадть что-то несвязанное

    prev_scammers - спикеры, которых ты подозревал в мошенничестве на всех предыдущих сегментах

    Формат выходных данных:

    {
        "call_number": number,
        "category": "normal" | "suspicious" | "fraudulent",
        "summary": string,
        "risk_score": number,
        "indicators": [string]
        "scammers": [string]
    }

    call_number - номер звонка, тот же что и у запроса

    category - категория звонка

    summary - общее описание текущего и всех предыдущих сегментов

    risk_score - риск-скор всего звонка

    indicators - индикаторы мошенничества, могут быть взяты из предыдущих сводок

    scammers - спикеры, являющиеся мошенниками (например, [SPEAKER_00, SPEAKER_01])

    !!! ВАЖНО !!!
    Ответь строго в формате JSON, без текста до или после.
    НЕ добавляй объяснения.
    НЕ добавляй рассуждения.
    НЕ добавляй вступления.
    Если формат нарушен — система завершит процесс.
    ТВОЙ ОТВЕТ ДОЛЖЕН БЫТЬ *ТОЛЬКО JSON*.

    Входные данные: {input_string}
    """

    s = s.replace("{input_string}", json.dumps({
        "call_number": call_number,
        "prev_summary": prev_summary,
        "segment": segment,
        "known_scammers_voice": ksv,
        "prev_risk_scores": prev_risc_scores,
        "prev_scammers": prev_scammers
    }, ensure_ascii=False))

    return s

# сегментация нужна, потому что на очень больших входных данных LLM не хватает контекста, и она выдает невалидный результат
def split_dialogue_into_segments(dialogue: list[str], max_segment_size: int = 4500) -> list[list[str]]:
    segments = []
    curr_segment = []
    curr_len = 0

    for dseg in dialogue:
        seg_len = len(dseg)

        if seg_len > max_segment_size:
            if curr_segment:
                segments.append(curr_segment)
                curr_segment = []
                curr_len = 0
            segments.append([dseg])
            curr_segment = []
            curr_len = 0
            continue

        if curr_len + seg_len <= max_segment_size:
            curr_segment.append(dseg)
            curr_len += seg_len
        else:
            segments.append(curr_segment)
            curr_segment = [dseg]
            curr_len = seg_len

    if curr_segment:
        segments.append(curr_segment)

    return segments

def send_reqular_request(dialogue: list[str], call_number: int, ksv: list[str], ollama_server, model: str | None = "ilyagusev/saiga_llama3"):
    prompt = generate_regular_prompt(dialogue, call_number, ksv)

    logging.debug(f"REGULAR PROMPT: {prompt}")

    return send_request(prompt, ollama_server, model)

def send_segmented_request(segments: list[list[str]], call_number: int, ksv: list[str], ollama_server, model: str | None = "ilyagusev/saiga_llama3"):
    segments_count = len(segments)
    prev_summary = None
    risk_scores = []
    scammers = set()

    for i in range(segments_count-1):
        prompt = generate_segment_propmt(prev_summary, segments[i], i+1, segments_count)
        logging.debug(f"SEGMENT PROMPT: {i}: {prompt}")
        resp = FilteringString(send_request(prompt, ollama_server, model)["response"]).filter(RegexFilter.md_json())

        logging.debug(f"SEGMENT RESPONSE: {i}: {resp}")

        parsed = json.loads(str(resp))

        prev_summary = parsed["summary"]
        risk_scores.append(parsed["segment_risk_score"])
        scammers.update(parsed["scammers"])

    return send_final_segmented_request(prev_summary, risk_scores, list(scammers), segments[segments_count-1], call_number, ksv, ollama_server, model)

def send_final_segmented_request(prev_summary: str | None, prev_risk_scores: list[int], prev_scammers: list[str], segment: list[str], call_number: int, ksv: list[str], ollama_server, model: str | None = "ilyagusev/saiga_llama3"):
    prompt = generate_final_segment_propmt(prev_summary, segment, call_number, ksv, prev_risk_scores, prev_scammers)
    logging.debug(f"FINAL SEGMENT PROMPT: {prompt}")

    return send_request(prompt, ollama_server, model)

def analyze_with_llm(dialogue: list[str], call_number: int, ksv: list[str], ollama_server, model: str | None = "ilyagusev/saiga_llama3"):
    segments = split_dialogue_into_segments(dialogue)

    if len(segments) == 1:
        return send_reqular_request(dialogue, call_number, ksv, ollama_server, model)

    return send_segmented_request(segments, call_number, ksv, ollama_server, model)

def send_request(prompt, ollama_server, model: str | None = "ilyagusev/saiga_llama3"):
    OLLAMA_GENERATE_PATH = "api/generate"
    resp = requests.post(f"{ollama_server}/{OLLAMA_GENERATE_PATH}", json={
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options":  {"temperature": 0}
    }, verify=False)

    res = resp.json()
    return res
