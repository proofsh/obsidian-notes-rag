"""systemd user-service management for `obsidian-rag watch` on Linux."""
from __future__ import annotations

import getpass
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

SERVICE_NAME = "obsidian-notes-rag-watch"
_CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
UNIT_PATH = _CONFIG_HOME / "systemd" / "user" / f"{SERVICE_NAME}.service"
ENV_FILE = _CONFIG_HOME / "obsidian-notes-rag" / "service.env"

# Env vars copied into the service's EnvironmentFile if set at install time.
PASSTHROUGH_VARS = (
    "OPENAI_API_KEY",
    "OBSIDIAN_RAG_PROVIDER",
    "OBSIDIAN_RAG_VAULT",
    "OBSIDIAN_RAG_DATA",
    "OBSIDIAN_RAG_OLLAMA_URL",
    "OBSIDIAN_RAG_LMSTUDIO_URL",
    "OBSIDIAN_RAG_MODEL",
)


def _systemctl(*args: str, check: bool = True, capture: bool = False):
    return subprocess.run(
        ["systemctl", "--user", *args], check=check, text=True, capture_output=capture
    )


def _check_systemd() -> None:
    if not shutil.which("systemctl"):
        raise RuntimeError("systemctl not found - this system doesn't appear to use systemd.")
    r = _systemctl("show-environment", check=False, capture=True)
    if r.returncode != 0:
        raise RuntimeError(
            "Can't reach the systemd user manager. Log in directly (or via SSH) as this "
            "user instead of using `su`/`sudo -u`, so XDG_RUNTIME_DIR and DBus are set."
        )


def _resolve_executable() -> str:
    """Find a stable path to the CLI (not an ephemeral uvx cache path)."""
    for name in ("obsidian-rag", "obsidian-notes-rag"):
        path = shutil.which(name)
        if path and "/.cache/uv/" not in path:
            return path
    argv0 = str(Path(sys.argv[0]).resolve())
    if "/.cache/uv/" in argv0:
        raise RuntimeError(
            "You're running from the uvx cache, which can change or be cleaned. Install "
            "permanently first:\n  uv tool install git+https://github.com/<you>/obsidian-notes-rag"
        )
    return argv0


def _write_env_file() -> bool:
    values = {k: os.environ[k] for k in PASSTHROUGH_VARS if os.environ.get(k)}
    if not values:
        return ENV_FILE.exists()
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for k, v in values.items():
        escaped = v.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'{k}="{escaped}"')
    # 0600: the file may contain an API key.
    fd = os.open(ENV_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines) + "\n")
    return True


def _ensure_linger() -> None:
    """Without linger, user services stop when the user logs out - bad on a server."""
    user = getpass.getuser()
    r = subprocess.run(
        ["loginctl", "show-user", user, "-p", "Linger"], text=True, capture_output=True
    )
    if "Linger=yes" in r.stdout:
        return
    r = subprocess.run(["loginctl", "enable-linger", user], text=True, capture_output=True)
    if r.returncode == 0:
        print(f"Enabled linger for {user} (service runs without an active login).")
    else:
        print(
            f"Warning: couldn't enable linger. The service will stop when you log out.\n"
            f"Fix with:  sudo loginctl enable-linger {user}"
        )


def install_service(vault: str | None = None, data: str | None = None) -> int:
    try:
        _check_systemd()
        exe = _resolve_executable()
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    cmd = [exe]
    if vault:
        cmd += ["--vault", str(Path(vault).expanduser().resolve())]
    if data:
        cmd += ["--data", str(Path(data).expanduser().resolve())]
    cmd.append("watch")

    has_env = _write_env_file()
    unit = f"""[Unit]
Description=obsidian-notes-rag vault watcher (auto-reindex on changes)

[Service]
Type=simple
ExecStart={shlex.join(cmd)}
{f"EnvironmentFile={ENV_FILE}" if has_env else ""}
Environment=PYTHONUNBUFFERED=1
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
"""
    UNIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    UNIT_PATH.write_text(unit)

    try:
        _systemctl("daemon-reload")
        _systemctl("enable", "--now", SERVICE_NAME)
    except subprocess.CalledProcessError as e:
        print(f"Error: systemctl failed ({e}).", file=sys.stderr)
        return 1

    _ensure_linger()
    print(f"Installed and started {SERVICE_NAME}")
    print(f"  Unit: {UNIT_PATH}")
    if has_env:
        print(f"  Env:  {ENV_FILE}")
    print(f"  Logs: journalctl --user -u {SERVICE_NAME} -f")
    return 0


def uninstall_service() -> int:
    _systemctl("disable", "--now", SERVICE_NAME, check=False, capture=True)
    if UNIT_PATH.exists():
        UNIT_PATH.unlink()
    _systemctl("daemon-reload", check=False)
    _systemctl("reset-failed", SERVICE_NAME, check=False, capture=True)
    print(f"Removed {SERVICE_NAME}.")
    if ENV_FILE.exists():
        print(f"Note: {ENV_FILE} was kept (may contain secrets; delete manually if unneeded).")
    return 0


def service_status() -> int:
    if not UNIT_PATH.exists():
        print("Service not installed. Run: obsidian-rag install-service")
        return 1
    enabled = _systemctl("is-enabled", SERVICE_NAME, check=False, capture=True).stdout.strip()
    active = _systemctl("is-active", SERVICE_NAME, check=False, capture=True).stdout.strip()
    pid = _systemctl(
        "show", SERVICE_NAME, "-p", "MainPID", "--value", check=False, capture=True
    ).stdout.strip()
    print(f"Service: {SERVICE_NAME}")
    print(f"  Enabled: {enabled}")
    print(f"  Active:  {active}" + (f" (PID {pid})" if pid and pid != "0" else ""))
    print(f"  Unit:    {UNIT_PATH}")
    print("\nRecent logs:")
    r = subprocess.run(
        ["journalctl", "--user", "-u", SERVICE_NAME, "-n", "15", "--no-pager"],
        text=True, capture_output=True,
    )
    out = r.stdout.strip()
    print(out or "  (no logs visible - on Debian you may need persistent journald storage "
                 "or membership in the systemd-journal group)")
    return 0 if active == "active" else 3
