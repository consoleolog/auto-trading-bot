import json
import logging
import pickle
from json import JSONDecodeError
from typing import Any

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

    async def get(self, key: str) -> Any:
        """
        캐시에서 값을 가져옵니다.

        Args:
            key: 캐시 키

        Returns:
            캐시된 값 또는 찾을 수 없는 경우 None
        """
        try:
            value = await self.redis_client.get(key)

            if value is None:
                return None

            # 먼저 JSON으로 디코딩 시도
            try:
                return json.loads(value)
            except (JSONDecodeError, ValueError, UnicodeDecodeError):
                # 복잡한 객체의 경우 pickle로 폴백
                try:
                    return pickle.loads(value)
                except Exception:
                    # 최종적으로 문자열로 폴백
                    try:
                        return value.decode("utf-8") if isinstance(value, bytes) else value
                    except UnicodeDecodeError:
                        # 디코딩 실패 시 원본 bytes 반환
                        return value

        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None

    # 하위 호환성을 위한 확장 버전:
    async def get_with_options(self, key: str, default: Any = None, decode_json: bool = True) -> Any:
        """
        옵션을 포함하여 캐시에서 값을 가져옵니다 (내부 사용).

        Args:
            key: 캐시 키
            default: 찾을 수 없는 경우 반환할 기본값
            decode_json: JSON 디코딩 시도 여부

        Returns:
            캐시된 값 또는 기본값
        """
        try:
            value = await self.redis_client.get(key)

            if value is None:
                return default

            if decode_json:
                try:
                    return json.loads(value)
                except (JSONDecodeError, ValueError, UnicodeDecodeError):
                    # 복잡한 객체의 경우 pickle로 폴백
                    try:
                        return pickle.loads(value)
                    except Exception:
                        # 최종적으로 문자열로 폴백
                        try:
                            return value.decode("utf-8") if isinstance(value, bytes) else value
                        except UnicodeDecodeError:
                            # 디코딩 실패 시 원본 bytes 반환
                            return value

            return value.decode("utf-8") if isinstance(value, bytes) else value

        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return default

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = 300,
    ) -> bool:
        """
        선택적 TTL과 함께 캐시에 값을 설정합니다.

        Args:
            key: 캐시 키
            value: 캐시할 값
            ttl: 초 단위 유효 시간 (기본값 300)
        """
        try:
            # 값 직렬화
            if isinstance(value, (dict, list)):
                serialized = json.dumps(value)
            elif isinstance(value, (str, int, float)):
                serialized = str(value).encode("utf-8")
            else:
                serialized = pickle.dumps(value)

            # TTL 과 함께 설정 (ttl 은 항상 제공됨)
            if ttl and ttl > 0:
                await self.redis_client.setex(key, ttl, serialized)
            else:
                # ttl 이 0이거나 음수인 경우, 만료 없이 설정
                await self.redis_client.set(key, serialized)

            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False

    async def delete(self, key: str | list[str]) -> bool:
        """
        캐시에서 키를 삭제합니다.

        Args:
            key: 삭제할 캐시 키 (문자열) 또는 키 목록 (리스트)

        Returns:
            성공 시 True, 실패 시 False
        """
        try:
            if isinstance(key, str):
                await self.redis_client.delete(key)
            else:
                await self.redis_client.delete(*key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """
        캐시에 키가 존재하는지 확인합니다.

        Args:
            key: 확인할 캐시 키

        Returns:
            키가 존재하면 True, 존재하지 않거나 오류 발생 시 False
        """
        try:
            return bool(await self.redis_client.exists(key))
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False

    async def invalidate(self, pattern: str) -> int:
        """
        패턴과 일치하는 모든 키를 무효화(삭제)합니다.

        Args:
            pattern: 삭제할 키의 패턴 (예: "user:*", "session:*")

        Returns:
            삭제된 키의 개수
        """
        try:
            keys = []
            async for key in self.redis_client.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                return await self.redis_client.delete(*keys)
            return 0

        except Exception as e:
            logger.error(f"Cache invalidate error for pattern {pattern}: {e}")
            return 0
