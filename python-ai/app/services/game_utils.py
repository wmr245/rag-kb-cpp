from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
    return f'{prefix}_{uuid4().hex[:12]}'


def dump_model(model: BaseModel) -> dict:
    return model.model_dump(mode='json')
