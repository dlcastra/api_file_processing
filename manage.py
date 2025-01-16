import os
import uuid

import typer
from passlib.hash import bcrypt

# from settings.config import logger
from management.utils import ShellCommandLogs, run_command

app = typer.Typer()
shell_logger = ShellCommandLogs()


@app.command()
def get_secret_key():
    try:
        if not os.path.exists(".env"):
            with open(".env", "w") as file:
                # logger.info("Created .env file in root directory")
                file.write("")

        with open(".env", "r") as file:
            # logger.info("Reading .env")
            env_content = file.read()

        if "SECRET_KEY=" in env_content:
            msg = "SECRET_KEY already exists in the .env file. The key will not be overwritten."
            log = shell_logger.warn_message(msg)
            typer.echo(log)
            return

        uuid_key = str(uuid.uuid4())
        hashed_key = bcrypt.hash(uuid_key)
        env_line = f"\nSECRET_KEY={hashed_key}\n"
        with open(".env", "a") as file:
            file.write(env_line)

        log = shell_logger.info_message("The key was successfully generated and written to .env")
        typer.echo(log)

    except Exception as e:
        typer.echo(f"Error: {e}")


@app.command()
def init_alembic():
    output = run_command("alembic stamp head")
    typer.echo(output)


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def makemigrations(ctx: typer.Context):
    command_args = ["alembic", "revision", "--autogenerate"] + list(ctx.args)
    command = " ".join(map(str, command_args))
    output = run_command(command)
    typer.echo(output)


@app.command()
def migrate():
    output = run_command("alembic upgrade head")
    typer.echo(output)


if __name__ == "__main__":
    app()
