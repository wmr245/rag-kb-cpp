import json
from pathlib import Path
from typing import Any, Dict, List

from app.core.config import GAME_DATA_DIR


_BASE_DIR = Path(GAME_DATA_DIR)
_KIND_DIRS = {
    'assistants': _BASE_DIR / 'assistants',
    'worldbooks': _BASE_DIR / 'worldbooks',
    'character_cards': _BASE_DIR / 'character_cards',
    'sessions': _BASE_DIR / 'sessions',
}


def ensure_game_storage() -> None:
    _BASE_DIR.mkdir(parents=True, exist_ok=True)
    for path in _KIND_DIRS.values():
        path.mkdir(parents=True, exist_ok=True)


def _record_path(kind: str, record_id: str) -> Path:
    if kind not in _KIND_DIRS:
        raise ValueError(f'unsupported game storage kind: {kind}')
    return _KIND_DIRS[kind] / f'{record_id}.json'


def save_record(kind: str, record_id: str, payload: Dict[str, Any]) -> None:
    ensure_game_storage()
    path = _record_path(kind, record_id)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def load_record(kind: str, record_id: str) -> Dict[str, Any] | None:
    path = _record_path(kind, record_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding='utf-8'))


def delete_record(kind: str, record_id: str) -> None:
    path = _record_path(kind, record_id)
    if path.exists():
        path.unlink()


def list_records(kind: str) -> List[Dict[str, Any]]:
    ensure_game_storage()
    path = _KIND_DIRS[kind]
    rows: List[Dict[str, Any]] = []
    for file_path in sorted(path.glob('*.json')):
        rows.append(json.loads(file_path.read_text(encoding='utf-8')))
    return rows
