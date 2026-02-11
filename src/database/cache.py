import logging

import redis.asyncio as redis
from redis.asyncio.client import Redis

logger = logging.getLogger(__name__)


class RedisCache:
    def __init__(self, host: str, port: int, password: str, db: int):
        self.host = host
        self.port = port
        self.password = password
        self.db = db

        self.redis_client: Redis | None = None
        self.is_connected = False

    async def connect(self) -> None:
        """Redis 서버에 연결을 수립합니다."""
        try:
            if self.password:
                redis_url = f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
            else:
                redis_url = f"redis://{self.host}:{self.port}/{self.db}"

            self.redis_client = await redis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=False,  # 디코딩을 직접 처리
                socket_keepalive=True,
                # Docker에서 EINVAL 오류를 발생시키는 문제있는 socket_keepalive_options 제거됨
                max_connections=50,
                health_check_interval=30,
            )

            # 연결 테스트
            await self.redis_client.ping()

            # 키 만료 알림 설정
            await self._setup_keyspace_notifications()

            self.is_connected = True
            logger.info(
                f"Successfully connected to "
                f"Redis cache at {redis_url.split('@')[-1] if '@' in redis_url else redis_url}"
            )

        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def disconnect(self) -> None:
        """Redis 연결을 종료합니다."""
        if self.redis_client:
            await self.redis_client.close()
            self.is_connected = False
            logger.info("Disconnected from Redis cache")

    async def _setup_keyspace_notifications(self) -> None:
        """캐시 만료 이벤트에 대한 keyspace 알림을 활성화합니다."""
        try:
            await self.redis_client.config_set("notify-keyspace-events", "Ex")
        except Exception as e:
            logger.warning(f"Could not set keyspace notifications: {e}")
