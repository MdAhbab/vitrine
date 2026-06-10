#!/usr/bin/env python3
"""
Vitrine cloud VM deploy using Docker.

Targets a single Ubuntu/Debian VM and brings up the complete site with
Docker Compose:

    Caddy container (80/443 + TLS) -> app container (FastAPI gateway + Vite dist)

The app container uses SQLite by default, persisted in a Docker volume. No
Postgres or native Python/npm build is required on the VM.

Sub-commands:
    python cloudrun.py deploy --domain vitrine.ahbab.dev [--seed]
    python cloudrun.py update [--domain vitrine.ahbab.dev]
    python cloudrun.py status
    python cloudrun.py logs [app|web]
    python cloudrun.py rollback
    python cloudrun.py teardown [--volumes]
"""
from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
import textwrap
from pathlib import Path

DEFAULT_DOMAIN = "vitrine.ahbab.dev"
DEFAULT_GATEWAY_PORT = 8000
COMPOSE_FILE = "docker-compose.cloud.yml"

DRY = False
APP_DIR = Path("/opt/vitrine")


def c(text: str, code: str) -> str:
    return text if not sys.stdout.isatty() else f"\033[{code}m{text}\033[0m"


def info(msg: str) -> None:
    print(c("* ", "36") + msg)


def ok(msg: str) -> None:
    print(c("+ ", "32") + msg)


def warn(msg: str) -> None:
    print(c("! ", "33") + msg)


def die(msg: str) -> None:
    sys.exit(c("x ", "31") + msg)


def run(
    cmd: list[str] | str,
    *,
    shell: bool = False,
    check: bool = True,
    timeout: int | None = None,
    cwd: Path | None = None,
) -> int:
    pretty = cmd if isinstance(cmd, str) else " ".join(cmd)
    if DRY:
        where = f" (cwd={cwd})" if cwd else ""
        print(c("  [dry-run] ", "90") + pretty + where)
        return 0
    info(pretty)
    try:
        return subprocess.run(
            cmd,
            shell=shell,
            check=check,
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
        ).returncode
    except subprocess.TimeoutExpired:
        die(f"Command timed out after {timeout}s: {pretty}")
        return 1


def sudo(cmd: list[str], *, check: bool = True, timeout: int | None = None, cwd: Path | None = None) -> int:
    return run(["sudo", *cmd], check=check, timeout=timeout, cwd=cwd)


def write_file(path: Path, content: str, *, root: bool = False, mode: str | None = None) -> None:
    if DRY:
        print(c(f"  [dry-run] write {path} ({len(content)} bytes)", "90"))
        return
    if root:
        p = subprocess.Popen(["sudo", "tee", str(path)], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL)
        p.communicate(content.encode())
        if p.returncode:
            die(f"Failed to write {path}")
    else:
        path.write_text(content)
    if mode:
        (sudo if root else run)(["chmod", mode, str(path)])
    ok(f"wrote {path}")


def require_linux() -> None:
    if platform.system() != "Linux" and not DRY:
        die("cloudrun.py provisions a Linux VM. Use --dry-run to preview elsewhere.")


def command_ok(cmd: list[str]) -> bool:
    if DRY:
        return True
    return subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def compose_base() -> list[str]:
    if command_ok(["sudo", "docker", "compose", "version"]):
        return ["sudo", "docker", "compose", "-f", COMPOSE_FILE]
    if command_ok(["sudo", "docker-compose", "version"]):
        return ["sudo", "docker-compose", "-f", COMPOSE_FILE]
    die("Docker Compose is not available after install.")
    return []


def compose(args: list[str], *, check: bool = True, timeout: int | None = None) -> int:
    return run([*compose_base(), *args], check=check, timeout=timeout, cwd=APP_DIR)


def install_docker() -> None:
    info("Installing Docker engine + Compose plugin if needed...")
    sudo(["apt-get", "update", "-y"])
    sudo([
        "apt-get",
        "install",
        "-y",
        "ca-certificates",
        "curl",
        "git",
        "rsync",
        "docker.io",
        "docker-compose-plugin",
    ], check=False, timeout=600)
    if not command_ok(["sudo", "docker", "version"]):
        warn("apt did not provide a working Docker install; falling back to Docker's install script.")
        run("curl -fsSL https://get.docker.com | sudo sh", shell=True, timeout=600)
    sudo(["systemctl", "enable", "--now", "docker"])
    ok("Docker is ready.")


def sync_checkout() -> None:
    info(f"Syncing this checkout to {APP_DIR}...")
    sudo(["mkdir", "-p", str(APP_DIR)])
    sudo([
        "rsync",
        "-a",
        "--delete",
        "--exclude",
        ".git",
        "--exclude",
        ".venv",
        "--exclude",
        "__pycache__",
        "--exclude",
        "node_modules",
        "--exclude",
        "frontend/node_modules",
        "--exclude",
        "files",
        f"{Path.cwd()}/",
        f"{APP_DIR}/",
    ])
    ok("Checkout synced.")


def _read_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def write_env_values(path: Path, values: dict[str, str]) -> None:
    lines = path.read_text().splitlines() if path.exists() else []
    out: list[str] = []
    seen: set[str] = set()
    for raw in lines:
        key = raw.split("=", 1)[0].strip() if "=" in raw and not raw.strip().startswith("#") else ""
        if key in values:
            out.append(f"{key}={values[key]}")
            seen.add(key)
        else:
            out.append(raw)
    for key, value in values.items():
        if key not in seen:
            out.append(f"{key}={value}")
    write_file(path, "\n".join(out).rstrip() + "\n", root=True, mode="600")


def ensure_cloud_env(domain: str) -> None:
    env_path = APP_DIR / ".env.cloud"
    if not DRY and not env_path.exists():
        source = APP_DIR / ".env"
        if not source.exists():
            source = APP_DIR / ".env.example"
        if source.exists():
            sudo(["cp", str(source), str(env_path)])
        else:
            write_file(env_path, "", root=True, mode="600")

    required = {
        "ENV": "prod",
        "FRONTEND_ORIGIN": f"https://{domain}",
        "PUBLIC_DOMAIN": domain,
        "DATABASE_URL": "sqlite+aiosqlite:////data/vitrine.db",
        "EVENT_BUS": "memory",
        "CACHE": "memory",
        "REDIS_URL": "redis://redis:6379/0",
        "FILES_ROOT": "files",
    }
    write_env_values(env_path, required)
    ok(f"Cloud env ready for https://{domain}.")


def caddyfile(domain: str) -> str:
    return textwrap.dedent(f"""\
        {{
            email admin@{domain}
        }}

        {domain} {{
            encode zstd gzip

            header {{
                X-Frame-Options "SAMEORIGIN"
                X-Content-Type-Options "nosniff"
                Referrer-Policy "strict-origin-when-cross-origin"
            }}

            handle_path /api/* {{
                reverse_proxy app:{DEFAULT_GATEWAY_PORT} {{
                    flush_interval -1
                    header_up X-Real-IP {{remote_host}}
                    header_up X-Forwarded-For {{remote_host}}
                    header_up X-Forwarded-Proto {{scheme}}
                }}
            }}

            handle {{
                reverse_proxy app:{DEFAULT_GATEWAY_PORT}
            }}
        }}
    """)


def compose_yaml() -> str:
    return textwrap.dedent(f"""\
        services:
          app:
            build:
              context: .
              dockerfile: Dockerfile
              args:
                VITE_API_BASE: /api
            image: vitrine-app:latest
            restart: unless-stopped
            env_file:
              - .env.cloud
            volumes:
              - vitrine-data:/data
              - vitrine-files:/app/files
            expose:
              - "{DEFAULT_GATEWAY_PORT}"
            healthcheck:
              test: ["CMD", "curl", "-fsS", "http://127.0.0.1:{DEFAULT_GATEWAY_PORT}/health"]
              interval: 30s
              timeout: 5s
              retries: 5
              start_period: 20s

          web:
            image: caddy:2-alpine
            restart: unless-stopped
            depends_on:
              app:
                condition: service_started
            ports:
              - "80:80"
              - "443:443"
              - "443:443/udp"
            volumes:
              - ./Caddyfile:/etc/caddy/Caddyfile:ro
              - caddy-data:/data
              - caddy-config:/config

        volumes:
          vitrine-data:
          vitrine-files:
          caddy-data:
          caddy-config:
    """)


def write_runtime_files(domain: str) -> None:
    write_file(APP_DIR / "Caddyfile", caddyfile(domain), root=True, mode="644")
    write_file(APP_DIR / COMPOSE_FILE, compose_yaml(), root=True, mode="644")


def docker_build() -> None:
    info("Building app image with Docker...")
    compose(["build", "--pull", "app"], timeout=1800)
    ok("Docker image built.")


def docker_up() -> None:
    info("Starting containers...")
    compose(["up", "-d", "--remove-orphans"], timeout=600)
    ok("Containers are running.")


def seed_if_requested(seed: bool) -> None:
    if not seed:
        return
    info("Seeding demo data inside the app container...")
    compose(["exec", "-T", "app", "python", "-m", "backend.seed"], check=False, timeout=300)


def resolve_domain(args: argparse.Namespace) -> str:
    if getattr(args, "domain", None):
        return args.domain
    env_path = APP_DIR / ".env.cloud"
    env = _read_env(env_path)
    return env.get("PUBLIC_DOMAIN") or DEFAULT_DOMAIN


def cmd_deploy(args: argparse.Namespace) -> int:
    require_linux()
    domain = resolve_domain(args)
    info(f"Deploying Vitrine to https://{domain} with Docker.")
    install_docker()
    sync_checkout()
    ensure_cloud_env(domain)
    write_runtime_files(domain)
    docker_build()
    docker_up()
    seed_if_requested(args.seed)
    cmd_status(args)
    ok(f"Deployed. Visit https://{domain}")
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    require_linux()
    domain = resolve_domain(args)
    info(f"Updating Docker deployment for https://{domain}...")
    install_docker()
    sync_checkout()
    ensure_cloud_env(domain)
    write_runtime_files(domain)
    docker_build()
    docker_up()
    cmd_status(args)
    ok("Updated and restarted.")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    compose(["ps"], check=False)
    compose(["exec", "-T", "app", "curl", "-fsS", f"http://127.0.0.1:{DEFAULT_GATEWAY_PORT}/health"], check=False)
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    service = args.service or "app"
    aliases = {
        "gateway": "app",
        "api": "app",
        "caddy": "web",
    }
    service = aliases.get(service, service)
    return compose(["logs", "-f", "--tail", "200", service], check=False)


def cmd_rollback(args: argparse.Namespace) -> int:
    warn("Rollback restarts the currently built Docker image. Re-deploy a previous checkout for a true code rollback.")
    compose(["restart"], check=False)
    return 0


def cmd_teardown(args: argparse.Namespace) -> int:
    cmd = ["down", "--remove-orphans"]
    if args.volumes:
        cmd.append("--volumes")
    compose(cmd, check=False)
    ok("Docker deployment stopped.")
    return 0


def main() -> int:
    global DRY, APP_DIR
    ap = argparse.ArgumentParser(description="Vitrine cloud VM deploy (Docker)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--app-dir", default=str(APP_DIR))
    ap.add_argument("--user", default="", help="deprecated; Docker deployment does not create a service user")
    ap.add_argument("--proxy", choices=["caddy", "nginx"], default="caddy", help="deprecated; Docker deployment uses Caddy")
    ap.add_argument("--gateway-port", type=int, default=DEFAULT_GATEWAY_PORT, help="deprecated; app listens on 8000 in Docker")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("deploy")
    p.add_argument("--domain", default=DEFAULT_DOMAIN)
    p.add_argument("--seed", action="store_true")
    p.add_argument("--workers", type=int, default=2, help="deprecated; monolith Docker deployment does not spawn worker units")
    p.set_defaults(func=cmd_deploy)

    u = sub.add_parser("update")
    u.add_argument("--domain")
    u.set_defaults(func=cmd_update)

    sub.add_parser("status").set_defaults(func=cmd_status)
    lp = sub.add_parser("logs")
    lp.add_argument("service", nargs="?")
    lp.set_defaults(func=cmd_logs)
    sub.add_parser("rollback").set_defaults(func=cmd_rollback)
    td = sub.add_parser("teardown")
    td.add_argument("--volumes", action="store_true", help="also delete SQLite/files/Caddy volumes")
    td.set_defaults(func=cmd_teardown)

    args = ap.parse_args()
    DRY = args.dry_run
    APP_DIR = Path(args.app_dir)
    if args.proxy != "caddy":
        warn("--proxy is ignored; Docker cloud deployment uses the Caddy container.")
    if args.gateway_port != DEFAULT_GATEWAY_PORT:
        warn("--gateway-port is ignored; the app container listens on 8000.")
    if args.user:
        warn("--user is ignored; Docker cloud deployment does not create a VM service user.")
    if DRY:
        warn("DRY-RUN: no changes will be made.\n")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
