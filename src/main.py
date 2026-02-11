import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.getcwd())

from src.config import ConfigManager, ConfigSchema

load_dotenv()

logger = logging.getLogger(__name__)


async def main():
    schema = ConfigSchema()
    schema.require("app.mode", str)
    schema.require("trading.markets", list[str])
    schema.require("trading.timeframes", list[str])
    schema.require("exchange.name", str)

    config = ConfigManager(schema, watch_interval=2.0)

    config.load_file("config/config.yaml", required=True)

    if config.get("exchange.executor_name") == "upbit":
        exchange_config = {
            "UPBIT_API_KEY": "upbit.api_key",
            "UPBIT_API_SECRET": "upbit.api_secret",
        }
    else:
        exchange_config = {}

    config.load_env(
        mapping={
            **exchange_config,
            # Timescale DB
            "DB_HOST": "database.host",
            "DB_PORT": "database.port",
            "DB_NAME": "database.database",
            "DB_USER": "database.user",
            "DB_PASSWORD": "database.password",
            # Redis Cache
            "REDIS_HOST": "redis.host",
            "REDIS_DB": "redis.database",
            "REDIS_PORT": "redis.port",
            "REDIS_PASSWORD": "redis.password",
        }
    )

    try:
        config.validate()
        logger.info("Configuration validated successfully")
    except Exception as exception:
        logger.error(f"Configuration validation failed: {exception}")
        raise

    # TODO: run application


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s | %(levelname)8s | %(name)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Run
    asyncio.run(main())
