import json

from app.config import ROOT_DIR


THREAD_STORE_PATH = ROOT_DIR / "data" / "pending_threads.json"
IN_MEMORY_THREADS: dict[str, dict[str, str]] = {}


def load_thread_message(thread_id: str) -> str | None:
    payload = _load_store()
    thread_data = payload.get(thread_id)
    if thread_data is None:
        return None
    return thread_data.get("message")


def save_thread_message(thread_id: str, user_id: str, message: str) -> None:
    payload = _load_store()
    payload[thread_id] = {
        "user_id": user_id,
        "message": message,
    }
    _write_store(payload)


def clear_thread_message(thread_id: str) -> None:
    payload = _load_store()
    if thread_id in payload:
        payload.pop(thread_id)
        _write_store(payload)


def _load_store() -> dict[str, dict[str, str]]:
    if IN_MEMORY_THREADS:
        return dict(IN_MEMORY_THREADS)
    if not THREAD_STORE_PATH.exists():
        return {}
    try:
        return json.loads(THREAD_STORE_PATH.read_text(encoding="utf-8"))
    except (PermissionError, OSError, json.JSONDecodeError):
        return dict(IN_MEMORY_THREADS)


def _write_store(payload: dict[str, dict[str, str]]) -> None:
    IN_MEMORY_THREADS.clear()
    IN_MEMORY_THREADS.update(payload)
    try:
        THREAD_STORE_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except PermissionError:
        pass
