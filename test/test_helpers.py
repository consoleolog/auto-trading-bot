import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.utils.helpers import measure_time, rate_limit, retry_async

# ============= retry_async =============


class TestRetryAsync:
    @pytest.mark.asyncio
    async def test_returns_result_on_first_success(self):
        """첫 번째 시도에서 성공하면 결과를 즉시 반환한다."""

        @retry_async(max_retries=3, delay=0)
        async def succeed():
            return "ok"

        assert await succeed() == "ok"

    @pytest.mark.asyncio
    async def test_retries_on_failure_then_succeeds(self):
        """실패 후 재시도에서 성공하면 결과를 반환한다."""
        call_count = 0

        @retry_async(max_retries=3, delay=0)
        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("not yet")
            return "ok"

        result = await fail_then_succeed()

        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_last_exception_after_max_retries(self):
        """최대 재시도 횟수를 초과하면 마지막 예외를 발생시킨다."""

        @retry_async(max_retries=2, delay=0)
        async def always_fail():
            raise ConnectionError("fail")

        with pytest.raises(ConnectionError, match="fail"):
            await always_fail()

    @pytest.mark.asyncio
    async def test_retries_exact_max_retries_times(self):
        """정확히 max_retries 횟수만큼 재시도한다."""
        call_count = 0

        @retry_async(max_retries=4, delay=0)
        async def count_calls():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("fail")

        with pytest.raises(RuntimeError):
            await count_calls()

        assert call_count == 4

    @pytest.mark.asyncio
    async def test_exponential_backoff_increases_delay(self):
        """exponential_backoff 활성화 시 대기 시간이 지수적으로 증가한다."""
        sleep_times = []

        @retry_async(max_retries=3, delay=1.0, exponential_backoff=True)
        async def always_fail():
            raise RuntimeError("fail")

        with patch("src.utils.helpers.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(RuntimeError):
                await always_fail()
            sleep_times = [call.args[0] for call in mock_sleep.call_args_list]

        assert sleep_times == [1.0, 2.0, 4.0]

    @pytest.mark.asyncio
    async def test_fixed_delay_without_exponential_backoff(self):
        """exponential_backoff 비활성화 시 대기 시간이 일정하다."""

        @retry_async(max_retries=3, delay=0.5, exponential_backoff=False)
        async def always_fail():
            raise RuntimeError("fail")

        with patch("src.utils.helpers.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(RuntimeError):
                await always_fail()
            sleep_times = [call.args[0] for call in mock_sleep.call_args_list]

        assert sleep_times == [0.5, 0.5, 0.5]

    @pytest.mark.asyncio
    async def test_logs_warning_on_each_retry(self, caplog):
        """재시도 시마다 경고 로그가 출력된다."""

        @retry_async(max_retries=2, delay=0)
        async def always_fail():
            raise ValueError("boom")

        with caplog.at_level("WARNING"), pytest.raises(ValueError):
            await always_fail()

        assert caplog.text.count("Attempt") == 2

    @pytest.mark.asyncio
    async def test_preserves_function_name(self):
        """데코레이터 적용 후에도 원본 함수 이름이 유지된다."""

        @retry_async()
        async def my_function():
            pass

        assert my_function.__name__ == "my_function"

    @pytest.mark.asyncio
    async def test_passes_arguments_to_wrapped_function(self):
        """래핑된 함수에 인자가 올바르게 전달된다."""

        @retry_async(max_retries=1, delay=0)
        async def add(a, b, extra=0):
            return a + b + extra

        assert await add(1, 2, extra=10) == 13


# ============= measure_time =============


class TestMeasureTime:
    @pytest.mark.asyncio
    async def test_async_function_returns_result(self):
        """async 함수의 반환값이 그대로 전달된다."""

        @measure_time
        async def compute():
            return 42

        assert await compute() == 42

    def test_sync_function_returns_result(self):
        """sync 함수의 반환값이 그대로 전달된다."""

        @measure_time
        def compute():
            return 42

        assert compute() == 42

    @pytest.mark.asyncio
    async def test_async_function_logs_elapsed_time(self, caplog):
        """async 함수 실행 후 소요 시간이 로깅된다."""

        @measure_time
        async def slow_task():
            await asyncio.sleep(0.01)

        with caplog.at_level("DEBUG"):
            await slow_task()

        assert "slow_task" in caplog.text
        assert "took" in caplog.text

    def test_sync_function_logs_elapsed_time(self, caplog):
        """sync 함수 실행 후 소요 시간이 로깅된다."""

        @measure_time
        def quick_task():
            return 1

        with caplog.at_level("DEBUG"):
            quick_task()

        assert "quick_task" in caplog.text
        assert "took" in caplog.text

    def test_formats_microseconds(self, caplog):
        """1ms 미만이면 μs 단위로 표시한다."""

        @measure_time
        def instant():
            pass

        with caplog.at_level("DEBUG"):
            instant()

        assert "μs" in caplog.text

    @pytest.mark.asyncio
    async def test_formats_milliseconds(self, caplog):
        """1ms 이상 1s 미만이면 ms 단위로 표시한다."""

        @measure_time
        async def medium_task():
            await asyncio.sleep(0.01)

        with caplog.at_level("DEBUG"):
            await medium_task()

        assert "ms" in caplog.text

    @pytest.mark.asyncio
    async def test_formats_seconds(self, caplog):
        """1s 이상이면 s 단위로 표시한다."""

        @measure_time
        async def slow_task():
            await asyncio.sleep(1.0)

        with patch("src.utils.helpers.time.perf_counter", side_effect=[0.0, 1.5]), caplog.at_level("DEBUG"):
            await slow_task()

        assert "s" in caplog.text
        assert "ms" not in caplog.text
        assert "μs" not in caplog.text

    @pytest.mark.asyncio
    async def test_async_preserves_function_name(self):
        """async 함수에 적용해도 원본 함수 이름이 유지된다."""

        @measure_time
        async def my_async_func():
            pass

        assert my_async_func.__name__ == "my_async_func"

    def test_sync_preserves_function_name(self):
        """sync 함수에 적용해도 원본 함수 이름이 유지된다."""

        @measure_time
        def my_sync_func():
            pass

        assert my_sync_func.__name__ == "my_sync_func"

    @pytest.mark.asyncio
    async def test_async_propagates_exception(self):
        """async 함수에서 예외 발생 시 그대로 전파된다."""

        @measure_time
        async def failing():
            raise ValueError("error")

        with pytest.raises(ValueError, match="error"):
            await failing()

    def test_sync_propagates_exception(self):
        """sync 함수에서 예외 발생 시 그대로 전파된다."""

        @measure_time
        def failing():
            raise ValueError("error")

        with pytest.raises(ValueError, match="error"):
            failing()


# ============= rate_limit =============


class TestRateLimit:
    @pytest.mark.asyncio
    async def test_allows_calls_within_limit(self):
        """호출 횟수가 제한 이내이면 즉시 실행된다."""
        call_count = 0

        @rate_limit(calls=3, period=1.0)
        async def action():
            nonlocal call_count
            call_count += 1

        for _ in range(3):
            await action()

        assert call_count == 3

    @pytest.mark.asyncio
    async def test_delays_when_limit_exceeded(self):
        """호출 횟수가 제한을 초과하면 대기 후 실행된다."""

        @rate_limit(calls=2, period=1.0)
        async def action():
            return "done"

        with patch("src.utils.helpers.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await action()
            await action()
            await action()  # 3번째 호출 시 rate limit 작동

        mock_sleep.assert_called()

    @pytest.mark.asyncio
    async def test_returns_result(self):
        """rate limit 이 적용되어도 함수 반환값이 정상 전달된다."""

        @rate_limit(calls=5, period=1.0)
        async def compute(x):
            return x * 2

        assert await compute(5) == 10

    @pytest.mark.asyncio
    async def test_preserves_function_name(self):
        """데코레이터 적용 후에도 원본 함수 이름이 유지된다."""

        @rate_limit()
        async def my_limited_func():
            pass

        assert my_limited_func.__name__ == "my_limited_func"
