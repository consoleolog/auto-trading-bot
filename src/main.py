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
    schema.require("trading_bot.mode", str)
    schema.require("exchanges.executor_name", str)

    config = ConfigManager(schema, watch_interval=2.0)

    config.load_file("config/trading_bot.yaml", required=True)
    config.load_file("config/database.yaml", required=True)

    if config.get("exchanges.executor_name") == "upbit":
        executor_config = {
            "UPBIT_API_KEY": "upbit.access_key",
            "UPBIT_API_SECRET": "upbit.secret_key",
        }
    else:
        executor_config = {}

    config.load_env(
        mapping={
            **executor_config,
            # Timescale DB
            "DB_HOST": "timescaledb.host",
            "DB_PORT": "timescaledb.port",
            "DB_NAME": "timescaledb.database",
            "DB_USER": "timescaledb.user",
            "DB_PASSWORD": "timescaledb.password",
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
