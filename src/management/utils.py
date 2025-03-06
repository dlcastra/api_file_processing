import subprocess

import typer


def run_command(command: str):
    """Function for executing shell commands"""
    try:
        result = subprocess.run(command, shell=True, check=True, text=True, capture_output=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"


class ShellCommandLogs:
    @staticmethod
    def info_message(msg: str) -> str:
        log = typer.style(msg, fg=typer.colors.GREEN)
        return log

    @staticmethod
    def warn_message(msg: str) -> str:
        log = typer.style(msg, fg=typer.colors.BRIGHT_YELLOW)
        return log

    @staticmethod
    def error_message(msg: str) -> str:
        log = typer.style(msg, fg=typer.colors.RED)
        return log

    @staticmethod
    def critical_message(msg: str) -> str:
        log = typer.style(msg, fg=typer.colors.BRIGHT_RED, bold=True)
        return log
