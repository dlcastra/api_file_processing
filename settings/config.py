import logging
import platform

from colorama import Fore, Style, init
from decouple import config
from pydantic_settings import BaseSettings

if platform.system() == "Windows":
    init(autoreset=True)


# Base settings
class Settings(BaseSettings):
    database_url: str = config("DATABASE_URL", "mock-db")
    SECRET_KEY: str = config("JWT_SECRET", "mock-jwt-secret")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 2


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


# console_handler = logging.StreamHandler()
# console_handler.setFormatter(ColorLogFormatter("%(levelname)s: %(message)s"))
# logging.basicConfig(level=logging.DEBUG, handlers=[console_handler])
# logger = logging.getLogger(__name__)

settings = Settings()
