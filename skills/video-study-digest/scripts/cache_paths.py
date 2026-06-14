#!/usr/bin/env python3
"""Cache path helpers for video-study-digest scripts."""

from __future__ import annotations

import os
from pathlib import Path


CACHE_ENV_VAR = "VIDEO_STUDY_CACHE_ROOT"


def default_cache_root(
    env: dict[str, str] | None = None,
    os_name: str | None = None,
    home: Path | None = None,
    path_exists=None,
) -> Path:
    environment = os.environ if env is None else env
    configured = environment.get(CACHE_ENV_VAR)
    if configured:
        return Path(configured).expanduser()

    platform = os.name if os_name is None else os_name
    home_dir = Path.home() if home is None else home
    path_exists = path_exists or (lambda path: path.exists())

    if platform == "nt":
        local_f_drive_cache = Path(r"F:\cc_project\CodexMediaCache")
        if path_exists(local_f_drive_cache):
            return local_f_drive_cache
        local_app_data = environment.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "video-study-digest"
        return home_dir / "AppData" / "Local" / "video-study-digest"

    xdg_cache_home = environment.get("XDG_CACHE_HOME")
    if xdg_cache_home:
        return Path(xdg_cache_home) / "video-study-digest"
    return home_dir / ".cache" / "video-study-digest"
