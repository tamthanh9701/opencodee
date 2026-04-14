import pytest

from claw_system.recovery import retry, MaxRetriesExceeded


async def _success_fn():
    return "ok"


async def _fail_fn():
    raise RuntimeError("always fails")


_call_count = 0


async def _fail_then_succeed():
    global _call_count
    _call_count += 1
    if _call_count < 3:
        raise RuntimeError(f"fail #{_call_count}")
    return "ok"


async def test_retry_success_first_try():
    result = await retry(_success_fn, max_retries=3, base_delay=0.01)
    assert result == "ok"


async def test_retry_exhausted():
    with pytest.raises(MaxRetriesExceeded) as exc_info:
        await retry(_fail_fn, max_retries=2, base_delay=0.01, backoff_factor=1.0)
    assert exc_info.value.attempts == 2


async def test_retry_succeeds_after_failures():
    global _call_count
    _call_count = 0
    result = await retry(_fail_then_succeed, max_retries=4, base_delay=0.01, backoff_factor=1.0)
    assert result == "ok"


async def test_retry_with_args():
    async def add(a, b):
        return a + b

    result = await retry(add, 3, 4, max_retries=1)
    assert result == 7