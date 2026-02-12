import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.getcwd())

from src.config import ConfigManager, ConfigSchema
from src.montioring import setup_logger
from src.trading.application import TradingApplication

load_dotenv()

logger = logging.getLogger(__name__)


async def main():
    schema = ConfigSchema()
    schema.require("app.mode", str)
    schema.require("logging", dict)
    schema.require("trading.markets", list)
    schema.require("trading.timeframes", list)
    schema.require("exchange.name", str)

    config = ConfigManager(schema, watch_interval=2.0)

    config.load_file("config/config.yaml", required=True)

    if config.get("exchange.name") == "upbit":
        exchange_config = {
            "UPBIT_API_KEY": "exchange.upbit.api_key",
            "UPBIT_API_SECRET": "exchange.upbit.api_secret",
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

    setup_logger(config=config)
    app = TradingApplication(config)

    try:
        await app.start()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s | %(levelname)8s | %(name)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Run
    asyncio.run(main())
