import uuid
from datetime import datetime, timezone

from core.config import settings


def success_response(
    data,
    latency_ms,
    message="Success"
):

    return {

        "success": True,

        "message": message,

        "data": data,

        "metadata": {

            "request_id": str(uuid.uuid4()),

            "model": settings.MODEL_NAME,

            "latency_ms": latency_ms,

            "timestamp": datetime.now(timezone.utc).isoformat()

        },

        "error": None

    }


def error_response(
    code,
    details,
    message="Request Failed"
):

    return {

        "success": False,

        "message": message,

        "data": None,

        "metadata": {

            "request_id": str(uuid.uuid4()),

            "model": settings.MODEL_NAME,

            "latency_ms": 0,

            "timestamp": datetime.now(timezone.utc).isoformat()

        },

        "error": {

            "code": code,

            "details": details

        }

    }
