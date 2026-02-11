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

    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        """
        캐시에서 여러 값을 한 번에 가져옵니다.

        Args:
            keys: 가져올 캐시 키 목록

        Returns:
            키-값 딕셔너리 (존재하지 않는 키는 결과에 포함되지 않음)
        """
        try:
            values = await self.redis_client.mget(keys)
            result = {}

            for key, value in zip(keys, values, strict=True):
                if value is not None:
                    try:
                        result[key] = json.loads(value)
                    except JSONDecodeError:
                        result[key] = value.decode("utf-8") if isinstance(value, bytes) else value

            return result

        except Exception as e:
            logger.error(f"Cache get_many error: {e}")
            return {}

    async def set_many(self, mapping: dict[str, Any], ttl: int | None = None) -> bool:
        """
        여러 키-값 쌍을 한 번에 설정합니다.

        Args:
            mapping: 설정할 키-값 딕셔너리
            ttl: 선택적 TTL (초 단위, None이면 만료 없음)

        Returns:
            성공 시 True, 실패 시 False
        """
        try:
            # 값 직렬화
            serialized = {}
            for key, value in mapping.items():
                if isinstance(value, (dict, list)):
                    serialized[key] = json.dumps(value)
                else:
                    serialized[key] = str(value).encode("utf-8")

            # 효율성을 위해 파이프라인 사용
            async with self.redis_client.pipeline() as pipe:
                for key, value in serialized.items():
                    if ttl:
                        await pipe.setex(key, ttl, value)
                    else:
                        await pipe.set(key, value)
                await pipe.execute()

            return True

        except Exception as e:
            logger.error(f"Cache set_many error: {e}")
            return False

    # 구조화된 데이터를 위한 해시 연산
    async def hget(self, name: str, key: str) -> Any | None:
        """
        해시에서 필드 값을 가져옵니다.

        Args:
            name: 해시 이름
            key: 가져올 필드 키

        Returns:
            필드 값 또는 찾을 수 없는 경우 None
        """
        try:
            value = await self.redis_client.hget(name, key)
            if value:
                try:
                    return json.loads(value)
                except JSONDecodeError:
                    return value.decode("utf-8") if isinstance(value, bytes) else value
            return None
        except Exception as e:
            logger.error(f"Cache hget error: {e}")
            return None

    async def hset(self, name: str, key: str, value: Any) -> bool:
        """
        해시에 필드 값을 설정합니다.

        Args:
            name: 해시 이름
            key: 설정할 필드 키
            value: 설정할 값

        Returns:
            성공 시 True, 실패 시 False
        """
        try:
            serialized = json.dumps(value) if isinstance(value, (dict, list)) else str(value).encode("utf-8")

            await self.redis_client.hset(name, key, serialized)
            return True
        except Exception as e:
            logger.error(f"Cache hset error: {e}")
            return False

    async def hgetall(self, name: str) -> dict[str, Any]:
        """
        해시의 모든 필드를 가져옵니다.

        Args:
            name: 해시 이름

        Returns:
            모든 필드-값 딕셔너리
        """
        try:
            data = await self.redis_client.hgetall(name)
            result = {}

            for key, value in data.items():
                key_str = key.decode("utf-8") if isinstance(key, bytes) else key
                try:
                    result[key_str] = json.loads(value)
                except JSONDecodeError:
                    result[key_str] = value.decode("utf-8") if isinstance(value, bytes) else value

            return result
        except Exception as e:
            logger.error(f"Cache hgetall error: {e}")
            return {}

    # 큐를 위한 리스트 연산
    async def lpush(self, key: str, value: Any) -> int:
        """
        리스트의 왼쪽에 값을 추가합니다.

        Args:
            key: 리스트 키
            value: 추가할 값

        Returns:
            리스트의 새로운 길이
        """
        try:
            serialized = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
            return await self.redis_client.lpush(key, serialized)
        except Exception as e:
            logger.error(f"Cache lpush error: {e}")
            return 0

    async def rpop(self, key: str) -> Any | None:
        """
        리스트의 오른쪽에서 값을 제거하고 반환합니다.

        Args:
            key: 리스트 키

        Returns:
            제거된 값 또는 리스트가 비어있는 경우 None
        """
        try:
            value = await self.redis_client.rpop(key)
            if value:
                try:
                    return json.loads(value)
                except JSONDecodeError:
                    return value.decode("utf-8") if isinstance(value, bytes) else value
            return None
        except Exception as e:
            logger.error(f"Cache rpop error: {e}")
            return None

    async def lrange(self, key: str, start: int, stop: int) -> list[Any]:
        """
        리스트에서 범위의 값들을 가져옵니다.

        Args:
            key: 리스트 키
            start: 시작 인덱스 (0부터 시작)
            stop: 종료 인덱스 (-1은 마지막 요소)

        Returns:
            지정된 범위의 값 리스트
        """
        try:
            values = await self.redis_client.lrange(key, start, stop)
            result = []

            for value in values:
                try:
                    result.append(json.loads(value))
                except JSONDecodeError:
                    result.append(value.decode("utf-8") if isinstance(value, bytes) else value)

            return result
        except Exception as e:
            logger.error(f"Cache lrange error: {e}")
            return []
