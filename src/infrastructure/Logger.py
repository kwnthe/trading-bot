from enum import Enum
from typing import TextIO
from datetime import datetime
import sys
from pathlib import Path
from src.utils.config import Config


class LogLevel(str, Enum):
    DEBUG = "DEBUG"        # internal calculations
    INFO = "INFO"          # detected structures / signals
    SIGNAL = "SIGNAL"      # trade-worthy signal
    WARNING = "WARNING"   # unexpected but handled
    ERROR = "ERROR"        # failures

class RepositoryName(str, Enum):
    ZONES = Config.zones_log_repo or "zones"
    WIP = "wip"

class RepositoryType(str, Enum):
    FILE = "FILE"

class StrategyLogger:
    repositories: dict[str, str]  # storing file paths instead of open file handles

    def __init__(self, repositories: dict[str, RepositoryType]):
        self.repositories = {}
        # Ensure logs directory exists
        logs_dir = Path("notebooks")
        logs_dir.mkdir(exist_ok=True)
        
        for repository_name, repository_type in repositories.items():
            if repository_type == RepositoryType.FILE:
                file_path = logs_dir / f"{repository_name.value}.html"
                self.repositories[repository_name] = str(file_path)
                # Ensure the file exists
                file_path.touch(exist_ok=True)
            else:
                raise ValueError(f"Unsupported repository type: {repository_type}")

    def log(
        self,
        level: LogLevel,
        message: str,
        repository_name: str,
        date: str = None
    ):
        file_path = Path(self.repositories[repository_name])
        # Read existing content (handle case where file doesn't exist yet)
        existing_content = ""
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                existing_content = f.read()
        # Write new content on top
        with open(file_path, 'w', encoding='utf-8') as f:
            date = date or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"{date} {level.value}: {message}<br />{existing_content}")
    
    @staticmethod
    def get_logger():
        return StrategyLogger(repositories={
            RepositoryName.ZONES: RepositoryType.FILE,
            RepositoryName.WIP: RepositoryType.FILE
            })