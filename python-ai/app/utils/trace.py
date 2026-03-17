import uuid

from fastapi import Request


def get_trace_id(request: Request) -> str:
    trace_id = request.headers.get("x-trace-id", "").strip()
    return trace_id or str(uuid.uuid4())
