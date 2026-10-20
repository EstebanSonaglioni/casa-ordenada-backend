import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import httpx

from app.config import settings

MAX_AUDIO_BYTES = 25 * 1024 * 1024
ALLOWED_AUDIO_TYPES = {"audio/webm", "audio/mp4", "audio/mpeg", "audio/ogg", "audio/wav", "audio/x-m4a"}


def is_supported_audio_type(content_type: str | None) -> bool:
    base_type = (content_type or "").split(";", 1)[0].strip().lower()
    return base_type in ALLOWED_AUDIO_TYPES


def _headers() -> dict[str, str]:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return {"Authorization": f"Bearer {settings.openai_api_key}"}


def _raise_for_openai(response: httpx.Response) -> None:
    if response.is_success:
        return
    try:
        detail = response.json().get("error", {}).get("message", "Unknown provider error")
    except ValueError:
        detail = response.text[:300] or "Unknown provider error"
    raise RuntimeError(f"OpenAI request failed ({response.status_code}): {detail}")


def transcribe(audio_path: Path) -> str:
    with audio_path.open("rb") as audio:
        response = httpx.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers=_headers(),
            files={"file": (audio_path.name, audio, "application/octet-stream")},
            data={"model": settings.openai_transcription_model, "language": "es", "response_format": "json"},
            timeout=90,
        )
    _raise_for_openai(response)
    text = response.json().get("text", "").strip()
    if not text:
        raise RuntimeError("No speech was detected in the audio")
    return text


def interpret(transcript: str, context: dict) -> dict:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "domain": {"type": "string", "enum": ["shopping", "exercise", "inventory", "unknown"]},
            "action": {"type": "string"},
            "summary": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "missing_fields": {"type": "array", "items": {"type": "string"}},
            "data": {"type": "object", "additionalProperties": False, "properties": {
                "requested_name": {"type": ["string", "null"]}, "quantity_requested": {"type": ["number", "null"]},
                "unit": {"type": ["string", "null"]}, "priority": {"type": ["string", "null"]}, "note": {"type": ["string", "null"]},
                "performed_on": {"type": ["string", "null"]}, "activity": {"type": ["string", "null"]},
                "duration_minutes": {"type": ["integer", "null"]}, "notes": {"type": ["string", "null"]},
                "product_id": {"type": ["integer", "null"]}, "storage_location_id": {"type": ["integer", "null"]},
                "quantity": {"type": ["number", "null"]}, "purchased_on": {"type": ["string", "null"]}, "expires_on": {"type": ["string", "null"]},
            }, "required": ["requested_name", "quantity_requested", "unit", "priority", "note", "performed_on", "activity", "duration_minutes", "notes", "product_id", "storage_location_id", "quantity", "purchased_on", "expires_on"]},
        },
        "required": ["domain", "action", "summary", "confidence", "missing_fields", "data"],
    }
    instructions = f"""Sos un asistente de Casa Ordenada. Interpretá la transcripción en español y proponé una única carga de datos. Nunca inventes IDs ni valores; si faltan datos, incluilos en missing_fields. Usá acciones permitidas: shopping.add_item, exercise.create, inventory.add_item. La propuesta se mostrará al usuario y no ejecuta nada. Contexto disponible de la casa: {json.dumps(context, ensure_ascii=False)}"""
    response = httpx.post(
        "https://api.openai.com/v1/responses",
        headers={**_headers(), "Content-Type": "application/json"},
        json={"model": settings.openai_interpretation_model, "instructions": instructions, "input": transcript, "text": {"format": {"type": "json_schema", "name": "assistant_command", "strict": True, "schema": schema}}},
        timeout=90,
    )
    _raise_for_openai(response)
    payload = response.json()
    output_text = "".join(
        item.get("text", "")
        for output in payload.get("output", [])
        for item in output.get("content", [])
        if item.get("type") == "output_text"
    )
    if not output_text:
        raise RuntimeError("The interpretation model returned no proposal")
    return json.loads(output_text)


def save_audio(content: bytes, suffix: str) -> Path:
    if len(content) > MAX_AUDIO_BYTES:
        raise ValueError("Audio file exceeds the 25 MB limit")
    directory = Path(settings.assistant_audio_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{uuid4().hex}{suffix}"
    path.write_bytes(content)
    return path


def expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=settings.assistant_audio_retention_days)
