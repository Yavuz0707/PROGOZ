from typing import Any, Optional

from pydantic import BaseModel


class ApiResponse(BaseModel):
    success: bool = True
    data: Optional[Any] = None
    message: str = ""


def ok(data: Any = None, message: str = "OK") -> dict:
    return {"success": True, "data": data, "message": message}


def fail(error: str, detail: str = "") -> dict:
    return {"success": False, "error": error, "detail": detail}

