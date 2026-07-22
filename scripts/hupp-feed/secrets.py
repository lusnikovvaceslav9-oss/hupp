"""Load secrets from environment or secrets.env file."""

from __future__ import annotations

import os
import re
from pathlib import Path


def read_secret(name: str, secrets_path: Path | None = None) -> str | None:
    env_val = os.environ.get(name, "").strip()
    if env_val:
        return env_val
    if secrets_path is None or not secrets_path.is_file():
        return None
    pattern = re.compile(rf"^\s*{re.escape(name)}\s*=\s*(.+)\s*$")
    for line in secrets_path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("#"):
            continue
        m = pattern.match(line)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    return None


def load_secrets(work_dir: Path) -> dict[str, str | None]:
    work_dir = work_dir.resolve()
    candidates = [
        work_dir / "secrets.env",
        Path(__file__).resolve().parents[2] / "secrets.env",
    ]
    seen: set[Path] = set()
    secret_files: list[Path] = []
    for p in candidates:
        rp = p.resolve()
        if rp in seen or not p.is_file():
            continue
        seen.add(rp)
        secret_files.append(p)

    keys = (
        "DIRECT_OAUTH_TOKEN",
        "DIRECT_CLIENT_LOGIN",
        "METRIKA_OAUTH_TOKEN",
        "METRIKA_COUNTER_ID",
        "METRIKA_GOAL_ID",
        "METRIKA_GOAL_ID_SECONDARY",
        "METRIKA_GOAL_ID_TERTIARY",
    )
    out: dict[str, str | None] = {}
    for key in keys:
        value = os.environ.get(key, "").strip() or None
        if value is None:
            for path in secret_files:
                value = read_secret(key, path)
                if value:
                    break
        out[key] = value
    # Same Yandex OAuth often covers both Direct and Metrika.
    if not out.get("METRIKA_OAUTH_TOKEN") and out.get("DIRECT_OAUTH_TOKEN"):
        out["METRIKA_OAUTH_TOKEN"] = out["DIRECT_OAUTH_TOKEN"]
    return out
