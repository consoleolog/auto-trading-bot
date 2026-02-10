from unittest.mock import AsyncMock, MagicMock

import pytest

from src.trading.exchanges.upbit.errors import (
    CreateAskError,
    CreateBidError,
    ExpiredAccessKeyError,
    InsufficientFundsAskError,
    InsufficientFundsBidError,
    InValidAccessKeyError,
    InvalidQueryPayloadError,
    JwtVerificationError,
    NoAutorizationIPError,
    NonceUsedError,
    OutOfScopeError,
    RemainingReqParsingError,
    TooManyRequestsError,
    UnderMinTotalAskError,
    UnderMinTotalBidError,
    UpbitBadRequestError,
    UpbitBaseError,
    UpbitError,
    UpbitLimitError,
    UpbitUnauthorizedError,
    ValidationError,
    WidthdrawAddressNotRegisterdError,
    error_handler,
)

# ============= UpbitBaseError =============


class TestUpbitBaseError:
    def test_stores_context_as_attributes(self):
        """키워드 인자가 인스턴스 속성으로 저장된다."""
        err = UpbitBaseError(name="test", code=400, msg="error")

        assert err.name == "test"
        assert err.code == 400
        assert err.msg == "error"

    def test_str_formats_with_context(self):
        """__str__이 컨텍스트 변수로 메시지를 포맷팅한다."""

        class CustomError(UpbitBaseError):
            name = "custom"
            code = 999
            msg = "{detail} 발생"

        err = CustomError(detail="타임아웃")

        assert str(err) == "타임아웃 발생"

    def test_str_returns_static_message(self):
        """포맷 변수가 없는 메시지는 그대로 반환된다."""
        err = CreateAskError()

        assert str(err) == "주문 요청 정보가 올바르지 않습니다."


# ============= Error Hierarchy =============


class TestErrorHierarchy:
    @pytest.mark.parametrize(
        "error_cls",
        [
            CreateAskError,
            CreateBidError,
            InsufficientFundsAskError,
            InsufficientFundsBidError,
            UnderMinTotalAskError,
            UnderMinTotalBidError,
            WidthdrawAddressNotRegisterdError,
            ValidationError,
        ],
    )
    def test_bad_request_errors_have_code_400(self, error_cls):
        """BadRequest 에러 클래스의 code가 400이다."""
        assert error_cls.code == 400
        assert issubclass(error_cls, UpbitBadRequestError)

    @pytest.mark.parametrize(
        "error_cls",
        [
            InvalidQueryPayloadError,
            JwtVerificationError,
            ExpiredAccessKeyError,
            NonceUsedError,
            NoAutorizationIPError,
            OutOfScopeError,
        ],
    )
    def test_unauthorized_errors_have_code_401(self, error_cls):
        """Unauthorized 에러 클래스의 code가 401이다."""
        assert error_cls.code == 401
        assert issubclass(error_cls, UpbitUnauthorizedError)

    def test_too_many_requests_error_has_code_429(self):
        """TooManyRequestsError의 code가 429이다."""
        assert TooManyRequestsError.code == 429
        assert issubclass(TooManyRequestsError, UpbitLimitError)

    def test_all_errors_inherit_from_base(self):
        """모든 에러가 UpbitBaseError를 상속한다."""
        all_errors = [
            CreateAskError,
            CreateBidError,
            InsufficientFundsAskError,
            InsufficientFundsBidError,
            UnderMinTotalAskError,
            UnderMinTotalBidError,
            WidthdrawAddressNotRegisterdError,
            ValidationError,
            InvalidQueryPayloadError,
            JwtVerificationError,
            ExpiredAccessKeyError,
            NonceUsedError,
            NoAutorizationIPError,
            OutOfScopeError,
            TooManyRequestsError,
            RemainingReqParsingError,
            InValidAccessKeyError,
        ]
        for err_cls in all_errors:
            assert issubclass(err_cls, UpbitBaseError)


# ============= error_handler =============


def _make_response(status: int, json_data: dict, text: str = "") -> AsyncMock:
    """테스트용 aiohttp 응답 mock 을 생성한다."""
    response = AsyncMock()
    response.status = status
    response.json = AsyncMock(return_value=json_data)
    response.text = AsyncMock(return_value=text)
    response.release = MagicMock()
    return response


class TestErrorHandler:
    @pytest.mark.asyncio
    async def test_returns_data_on_success(self):
        """에러가 없으면 JSON 데이터를 그대로 반환한다."""

        @error_handler
        async def api_call():
            return _make_response(200, {"result": "ok"})

        result = await api_call()

        assert result == {"result": "ok"}

    @pytest.mark.asyncio
    async def test_returns_list_data(self):
        """응답이 리스트인 경우 그대로 반환한다."""

        @error_handler
        async def api_call():
            return _make_response(200, [{"id": 1}, {"id": 2}])

        result = await api_call()

        assert result == [{"id": 1}, {"id": 2}]

    @pytest.mark.asyncio
    async def test_raises_bad_request_error_on_400(self):
        """400 응답 시 매칭되는 UpbitBadRequestError를 발생시킨다."""

        @error_handler
        async def api_call():
            return _make_response(
                400,
                {"error": {"name": "create_ask_error", "message": "error"}},
            )

        with pytest.raises(CreateAskError):
            await api_call()

    @pytest.mark.asyncio
    async def test_raises_unauthorized_error_on_401(self):
        """401 응답 시 매칭되는 UpbitUnauthorizedError를 발생시킨다."""

        @error_handler
        async def api_call():
            return _make_response(
                401,
                {"error": {"name": "jwt_verification", "message": "error"}},
            )

        with pytest.raises(JwtVerificationError):
            await api_call()

    @pytest.mark.asyncio
    async def test_raises_too_many_requests_on_429(self):
        """429 응답 시 TooManyRequestsError를 발생시킨다."""

        @error_handler
        async def api_call():
            return _make_response(
                429,
                {"error": {"name": "too_many", "message": "limit"}},
                text="Too many API requests.",
            )

        with pytest.raises(TooManyRequestsError):
            await api_call()

    @pytest.mark.asyncio
    async def test_raises_upbit_error_on_unknown_status(self):
        """알 수 없는 상태 코드의 에러 응답 시 UpbitError를 발생시킨다."""

        @error_handler
        async def api_call():
            return _make_response(
                500,
                {"error": {"name": "server_error", "message": "내부 서버 오류"}},
            )

        with pytest.raises(UpbitError):
            await api_call()

    @pytest.mark.asyncio
    async def test_releases_response_on_success(self):
        """정상 응답 시 response.release()가 호출된다."""
        mock_response = _make_response(200, {"result": "ok"})

        @error_handler
        async def api_call():
            return mock_response

        await api_call()

        mock_response.release.assert_called_once()

    @pytest.mark.asyncio
    async def test_releases_response_on_error(self):
        """에러 응답 시에도 response.release()가 호출된다."""
        mock_response = _make_response(
            400,
            {"error": {"name": "create_ask_error", "message": "error"}},
        )

        @error_handler
        async def api_call():
            return mock_response

        with pytest.raises(CreateAskError):
            await api_call()

        mock_response.release.assert_called_once()

    @pytest.mark.asyncio
    async def test_preserves_function_name(self):
        """데코레이터 적용 후에도 원본 함수 이름이 유지된다."""

        @error_handler
        async def my_api_call():
            pass

        assert my_api_call.__name__ == "my_api_call"

    @pytest.mark.asyncio
    async def test_passes_arguments_to_wrapped_function(self):
        """래핑된 함수에 인자가 올바르게 전달된다."""

        @error_handler
        async def api_call(market, count=10):
            return _make_response(200, {"market": market, "count": count})

        result = await api_call("KRW-BTC", count=5)

        assert result == {"market": "KRW-BTC", "count": 5}
