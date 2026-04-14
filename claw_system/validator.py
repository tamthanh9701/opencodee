from typing import Type, TypeVar

import structlog
from pydantic import BaseModel, ValidationError

from claw_system.models import TaskResult

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


def validate_output(schema: Type[T], data: dict) -> TaskResult[T]:
    try:
        parsed = schema.model_validate(data)
        logger.info(
            "output_validated",
            schema=schema.__name__,
            fields=list(data.keys()),
        )
        return TaskResult(
            status="success",
            data=parsed,
        )
    except ValidationError as e:
        error_msg = str(e)
        logger.warning(
            "output_validation_failed",
            schema=schema.__name__,
            error=error_msg,
        )
        return TaskResult(
            status="error",
            error=error_msg,
        )