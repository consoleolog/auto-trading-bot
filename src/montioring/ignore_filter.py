import logging


class IgnorePortScannersFilter(logging.Filter):
    """
    aiohttp에서 발생하는 무해한 포트 스캐너 에러를 무시하는 필터

    이런 에러들은 봇/스캐너가 HTTP 포트에 다른 프로토콜(SSL, SSH, SOCKS 등)을
    시도할 때 발생합니다.

    완전히 무해하며 로그에 노이즈만 추가합니다.
    """

    # 무시할 패턴들
    IGNORED_PATTERNS = [
        "BadStatusLine",  # 잘못된 HTTP
        "Invalid method encountered",  # 비-HTTP 프로토콜 시도
        "Error handling request",  # aiohttp 에러 래퍼
    ]

    # 포트 스캐너의 바이트 패턴들 (16진수 표현)
    SCANNER_BYTES = [
        "\\x16\\x03\\x01",  # SSL/TLS handshake
        "\\x04\\x01",  # SOCKS4 요청
        "\\x05\\x01",  # SOCKS5 요청
        "SSH-2.0",  # SSH 스캐너
        "GET / HTTP",  # 때로는 정상이지만 대부분 스캐너
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """
        레코드를 필터링(로그하지 않음)하려면 False 반환
        레코드를 로그하려면 True 반환

        Args:
            record: 평가할 로그 레코드

        Returns:
            레코드를 필터링해야 하면 False, 그렇지 않으면 True
        """
        # aiohttp.server 로거만 필터링
        if "aiohttp.server" not in record.name:
            return True  # aiohttp 외의 모든 로그는 허용

        # 로그 메시지 가져오기
        message = record.getMessage() if hasattr(record, "getMessage") else str(record.msg)

        # 포트 스캐너 에러인지 확인
        for pattern in self.IGNORED_PATTERNS:
            if pattern in message:
                # 스캐너 바이트 패턴이 메시지에 있는지 확인
                for scanner_byte in self.SCANNER_BYTES:
                    if scanner_byte in message:
                        # 포트 스캐너이므로 필터링
                        return False

                # "Invalid method"와 바이트 시퀀스가 함께 있으면 필터링
                if "Invalid method" in message and ("b'" in message or 'b"' in message):
                    return False

        # 다른 모든 aiohttp 에러는 허용
        return True
