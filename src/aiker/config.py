from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    root_dir: Path
    data_dir: Path
    projects_dir: Path
    db_file: Path

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_file.as_posix()}"


def get_app_paths() -> AppPaths:
    configured_home = os.getenv("AIKER_HOME")
    if configured_home:
        root_dir = Path(configured_home).expanduser().resolve()
    else:
        root_dir = Path(__file__).resolve().parents[2]

    data_dir = root_dir / "data"
    projects_dir = root_dir / "projects"
    db_file = data_dir / "aiker.db"
    return AppPaths(root_dir=root_dir, data_dir=data_dir, projects_dir=projects_dir, db_file=db_file)


def ensure_directories(paths: AppPaths) -> None:
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    paths.projects_dir.mkdir(parents=True, exist_ok=True)
