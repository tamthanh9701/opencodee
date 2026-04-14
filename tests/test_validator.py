from pydantic import BaseModel

from claw_system.validator import validate_output


class SampleSchema(BaseModel):
    name: str
    value: int


def test_validate_success():
    result = validate_output(SampleSchema, {"name": "test", "value": 42})
    assert result.status == "success"
    assert result.data is not None
    assert result.data.name == "test"
    assert result.data.value == 42
    assert result.error is None


def test_validate_failure():
    result = validate_output(SampleSchema, {"name": "test"})
    assert result.status == "error"
    assert result.data is None
    assert result.error is not None
    assert "value" in result.error.lower() or "missing" in result.error.lower()


def test_validate_wrong_types():
    result = validate_output(SampleSchema, {"name": "test", "value": "not_an_int"})
    assert result.status == "error"
    assert result.data is None