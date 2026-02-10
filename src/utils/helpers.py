import asyncio
import logging
import time
from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# ============= Decorators =============


def retry_async(max_retries: int = 3, delay: float = 1.0, exponential_backoff: bool = True) -> Callable[[F], F]:
    """
    비동기 함수에 재시도 로직을 적용하는 데코레이터.

    함수 호출이 예외를 발생시키면 지정된 횟수만큼 재시도한다.
    모든 재시도가 실패하면 마지막 예외를 그대로 발생시킨다.

    Args:
        max_retries: 최대 재시도 횟수 (기본값 3)
        delay: 재시도 간 대기 시간 (초, 기본값 1.0)
        exponential_backoff: True 이면 대기 시간이 지수적으로 증가 (delay * 2^attempt)

    Returns:
        데코레이터 함수
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: BaseException | None = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except (Exception, asyncio.TimeoutError) as exception:
                    last_exception = exception
                    wait_time: float = delay * (2**attempt) if exponential_backoff else delay
                    logger.warning(f"⚠️ Attempt {attempt + 1} failed: {exception}. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
            raise last_exception

        return async_wrapper

    return decorator


def measure_time(func: F) -> F:
    """
    함수의 실행 시간을 측정하여 로깅하는 데코레이터.

    async 함수와 sync 함수 모두 지원한다.
    소요 시간에 따라 μs, ms, s 단위로 자동 포맷팅한다.

    Args:
        func: 실행 시간을 측정할 대상 함수

    Returns:
        래핑된 함수 (async 또는 sync)
    """

    def format_elapsed(elapsed: float) -> str:
        if elapsed < 0.001:
            return f"{elapsed * 1000000:.2f} μs"
        elif elapsed < 1:
            return f"{elapsed * 1000:.2f} ms"
        else:
            return f"{elapsed:.4f} s"

    @wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        start: float = time.perf_counter()
        try:
            result = await func(*args, **kwargs)
            return result
        finally:
            elapsed: float = time.perf_counter() - start
            logger.debug(f"⏳ {func.__name__} took {format_elapsed(elapsed)}")

    @wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        start: float = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            elapsed: float = time.perf_counter() - start
            logger.debug(f"⏳ {func.__name__} took {format_elapsed(elapsed)}")

    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


def rate_limit(calls: int = 10, period: float = 1.0) -> Callable[[F], F]:
    """
    비동기 함수에 호출 빈도 제한을 적용하는 데코레이터.

    지정된 시간(period) 내에 최대 호출 횟수(calls)를 초과하면,
    다음 호출이 허용될 때까지 자동으로 대기한다.

    Args:
        calls: period 동안 최대로 호출할 수 있는 횟수 (기본값 10)
        period: 측정할 시간의 폭 (초, 기본값 1.0)

    Returns:
        데코레이터 함수
    """

    def decorator(func: Callable[..., Coroutine[Any, Any, Any]]) -> Callable[..., Coroutine[Any, Any, Any]]:
        calls_made: list[float] = []

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            now: float = time.time()
            nonlocal calls_made
            calls_made = [t for t in calls_made if now - t < period]

            if len(calls_made) >= calls:
                sleep_time: float = period - (now - calls_made[0])
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                    calls_made.clear()

            calls_made.append(time.time())
            return await func(*args, **kwargs)

        return wrapper

    return decorator
