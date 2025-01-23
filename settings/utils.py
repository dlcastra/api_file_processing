import os


def get_database_url() -> str:
    if os.getenv("DOCKERIZED", False):
        return (
            f"postgresql+asyncpg://{os.getenv('POSTGRES_USER', 'postgres')}:"
            f"{os.getenv('POSTGRES_PASSWORD', 'password')}@"
            f"{os.getenv('POSTGRES_HOST', 'db')}/"
            f"{os.getenv('POSTGRES_DB', 'postgres')}"
        )
    else:
        return "postgresql+asyncpg://postgres:password@localhost/file_processing"
