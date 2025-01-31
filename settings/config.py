import logging
import platform

import redis.asyncio as aioredis
from colorama import Fore, Style, init
from decouple import config
from pydantic_settings import BaseSettings
from starlette.templating import Jinja2Templates

if platform.system() == "Windows":
    init(autoreset=True)

# Base settings
local_db = "postgresql+asyncpg://postgres:password@localhost/file_processing"


class Settings(BaseSettings):
    SECRET_KEY: str = config("SECRET_KEY", "mock-secret-key")

    # Database settings
    DATABASE_URL: str = config("DATABASE_URL", local_db)

    # AWS settings
    AWS_ACCESS_KEY_ID: str = config("AWS_ACCESS_KEY_ID", "mock-access-key")
    AWS_SECRET_ACCESS_KEY: str = config("AWS_SECRET_ACCESS_KEY", "mock-secret-key")
    AWS_S3_BUCKET_NAME: str = config("AWS_S3_BUCKET_NAME", "mock-bucket")
    AWS_REGION: str = config("AWS_REGION", "us-east-1")


# Logger settings
class ColorLogFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: Fore.BLUE,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.LIGHTYELLOW_EX,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.RED + Style.BRIGHT,
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, "")
        message = super().format(record)
        return f"{color}{message}{Style.RESET_ALL}"


console_handler = logging.StreamHandler()
console_handler.setFormatter(ColorLogFormatter("%(levelname)s: %(message)s"))
logging.basicConfig(level=logging.DEBUG, handlers=[console_handler])
logger = logging.getLogger(__name__)

# Redis settings
redis = aioredis.from_url("redis://redis:6379/1")

# Template dir
templates = Jinja2Templates(directory="templates")

settings = Settings()
