#!/usr/bin/env python3
"""
Vitrine cloud runner — deploy the whole stack on a Linux VM with Docker.

The intended workflow is dead simple:

    git pull            # the repo already ships the seeded vitrine.db
    python3 run_onVM.py # installs Docker, builds, and serves https://vitrine.ahbab.dev

`python3 run_onVM.py` with no arguments runs a full deploy. Subcommands are
available for day-2 operations:

    python3 run_onVM.py deploy [--no-cache] [--seed]
    python3 run_onVM.py update [--no-cache]
    python3 run_onVM.py status
    python3 run_onVM.py logs [app|web]
    python3 run_onVM.py rollback
    python3 run_onVM.py teardown [--volumes]
    python3 run_onVM.py --dry-run deploy     # preview commands anywhere

Reverse proxy + TLS is handled by nginx (jonasal/nginx-certbot), which fetches
and auto-renews Let's Encrypt certificates for the domain. The app container is
never published to the host — only nginx binds :80/:443.

The database ships seeded inside the repo (vitrine.db). On a fresh volume the
container copies it into /data, so there is no separate seed step on the VM.
"""
from __future__ import annotations

import argparse
import platform
import subprocess
import sys
import textwrap
import time
from pathlib import Path

DEFAULT_DOMAIN = "vitrine.ahbab.dev"
DEFAULT_EMAIL = "admin@vitrine.ahbab.dev"
DEFAULT_GATEWAY_PORT = 8000
COMPOSE_FILE = "docker-compose.cloud.yml"
NGINX_FILE = "nginx.conf"

DRY = False
APP_DIR = Path("/opt/vitrine")


# ── tiny pretty-printers ───────────────────────────────────────────────────
def _c(text: str, code: str) -> str:
    return text if not sys.stdout.isatty() else f"\033[{code}m{text}\033[0m"


def info(msg: str) -> None:
    print(_c("* ", "36") + msg)


def ok(msg: str) -> None:
    print(_c("+ ", "32") + msg)


def warn(msg: str) -> None:
    print(_c("! ", "33") + msg)


def die(msg: str) -> None:
    sys.exit(_c("x ", "31") + msg)


# ── shell helpers ──────────────────────────────────────────────────────────
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
        print(_c("  [dry-run] ", "90") + pretty + where)
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
        print(_c(f"  [dry-run] write {path} ({len(content)} bytes)", "90"))
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
        die("run_onVM.py provisions a Linux VM. Use --dry-run to preview elsewhere.")


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


# ── provisioning ───────────────────────────────────────────────────────────
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
        # Exclude dev cruft, but KEEP vitrine.db — it is the seeded database.
        "--exclude", ".git",
        "--exclude", ".venv",
        "--exclude", "__pycache__",
        "--exclude", ".pytest_cache",
        "--exclude", "node_modules",
        "--exclude", "frontend/node_modules",
        "--exclude", "frontend/dist",
        "--exclude", "files",
        "--exclude", "vitrine.db-wal",
        "--exclude", "vitrine.db-shm",
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
        "FILES_ROOT": "files",
    }
    write_env_values(env_path, required)
    ok(f"Cloud env ready for https://{domain}.")


# ── runtime files (nginx + compose) ────────────────────────────────────────
def nginx_conf(domain: str) -> str:
    """nginx server blocks consumed by jonasal/nginx-certbot.

    The image auto-provisions and renews Let's Encrypt certs for every domain
    referenced by an `ssl_certificate` line, serving the ACME http-01 challenge
    from the webroot below. /api/* is prefix-stripped before it hits the gateway
    (mirrors the old Caddy `handle_path /api/*`), and the API location disables
    buffering so Server-Sent Events (Concierge / negotiate) stream in real time.
    """
    return textwrap.dedent(f"""\
        # Generated by run_onVM.py — do not edit by hand.
        # TLS is managed automatically by jonasal/nginx-certbot (Let's Encrypt).

        server {{
            listen 80;
            listen [::]:80;
            server_name {domain};

            # ACME http-01 challenge (certbot webroot)
            location /.well-known/acme-challenge/ {{
                root /var/www/letsencrypt;
            }}

            location / {{
                return 301 https://$host$request_uri;
            }}
        }}

        server {{
            listen 443 ssl;
            listen [::]:443 ssl;
            http2 on;
            server_name {domain};

            ssl_certificate     /etc/letsencrypt/live/{domain}/fullchain.pem;
            ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;

            add_header X-Frame-Options "SAMEORIGIN" always;
            add_header X-Content-Type-Options "nosniff" always;
            add_header Referrer-Policy "strict-origin-when-cross-origin" always;

            gzip on;
            gzip_vary on;
            gzip_proxied any;
            gzip_types text/plain text/css application/json application/javascript
                       application/xml text/xml image/svg+xml;

            # README / screenshot uploads
            client_max_body_size 25m;

            # API → gateway, strip the /api prefix.
            location /api/ {{
                proxy_pass http://app:{DEFAULT_GATEWAY_PORT}/;
                proxy_http_version 1.1;
                proxy_set_header Host $host;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                proxy_set_header X-Forwarded-Proto $scheme;

                # Server-Sent Events: stream, never buffer.
                proxy_buffering off;
                proxy_cache off;
                proxy_read_timeout 3600s;
                proxy_set_header Connection "";
            }}

            # Everything else → gateway (serves the built SPA and /files).
            location / {{
                proxy_pass http://app:{DEFAULT_GATEWAY_PORT};
                proxy_http_version 1.1;
                proxy_set_header Host $host;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                proxy_set_header X-Forwarded-Proto $scheme;
            }}
        }}
    """)


def compose_yaml(domain: str, email: str) -> str:
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
            # Internal only — never published to the host; nginx is the front door.
            expose:
              - "{DEFAULT_GATEWAY_PORT}"
            healthcheck:
              test: ["CMD", "curl", "-fsS", "http://127.0.0.1:{DEFAULT_GATEWAY_PORT}/health"]
              interval: 30s
              timeout: 5s
              retries: 5
              start_period: 20s

          web:
            image: jonasal/nginx-certbot:latest
            restart: unless-stopped
            depends_on:
              app:
                condition: service_started
            environment:
              CERTBOT_EMAIL: "{email}"
            ports:
              - "80:80"
              - "443:443"
            volumes:
              - ./{NGINX_FILE}:/etc/nginx/user_conf.d/vitrine.conf:ro
              - nginx-letsencrypt:/etc/letsencrypt

        volumes:
          vitrine-data:
          vitrine-files:
          nginx-letsencrypt:
    """)


def write_runtime_files(domain: str, email: str) -> None:
    write_file(APP_DIR / NGINX_FILE, nginx_conf(domain), root=True, mode="644")
    write_file(APP_DIR / COMPOSE_FILE, compose_yaml(domain, email), root=True, mode="644")


# ── docker lifecycle ───────────────────────────────────────────────────────
def docker_build(no_cache: bool = False) -> None:
    info("Building app image with Docker...")
    args = ["build", "--pull"]
    if no_cache:
        args.append("--no-cache")
    args.append("app")
    compose(args, timeout=1800)
    ok("Docker image built.")


def docker_up() -> None:
    info("Starting containers...")
    compose(["up", "-d", "--remove-orphans"], timeout=600)
    ok("Containers are running.")


def docker_prune() -> None:
    # The frontend is compiled in a throwaway node stage; once the final image
    # is built those intermediate/builder layers are pure dead weight (this is
    # what balloons the VM to ~2 GB). Reclaim them after every deploy.
    info("Reclaiming disk: pruning dangling images and build cache...")
    sudo(["docker", "image", "prune", "-f"], check=False)
    sudo(["docker", "builder", "prune", "-f"], check=False)
    ok("Pruned unused Docker layers.")


def seed_if_requested(seed: bool) -> None:
    # Not needed for a normal deploy — the repo ships a seeded vitrine.db and the
    # container loads it onto a fresh volume. `--seed` is only an escape hatch.
    if not seed:
        return
    info("Re-seeding demo data inside the app container...")
    for _ in range(15):
        r = subprocess.run(
            [*compose_base(), "ps", "app", "--format", "json"],
            capture_output=True, text=True, cwd=str(APP_DIR),
        )
        if '"Health":"healthy"' in r.stdout:
            break
        time.sleep(2)
    compose(["exec", "-T", "app", "python", "-m", "backend.seed"], check=False, timeout=300)


# ── commands ───────────────────────────────────────────────────────────────
def resolve_domain(args: argparse.Namespace) -> str:
    if getattr(args, "domain", None):
        return args.domain
    env = _read_env(APP_DIR / ".env.cloud")
    return env.get("PUBLIC_DOMAIN") or DEFAULT_DOMAIN


def resolve_email(args: argparse.Namespace, domain: str) -> str:
    return getattr(args, "email", None) or f"admin@{domain}"


def cmd_deploy(args: argparse.Namespace) -> int:
    require_linux()
    domain = resolve_domain(args)
    email = resolve_email(args, domain)
    info(f"Deploying Vitrine to https://{domain} with Docker + nginx.")
    install_docker()
    sync_checkout()
    ensure_cloud_env(domain)
    write_runtime_files(domain, email)
    docker_build(no_cache=getattr(args, "no_cache", False))
    docker_up()
    seed_if_requested(getattr(args, "seed", False))
    docker_prune()
    cmd_status(args)
    ok(f"Deployed. Visit https://{domain}")
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    require_linux()
    domain = resolve_domain(args)
    email = resolve_email(args, domain)
    info(f"Updating deployment for https://{domain}...")
    install_docker()
    sync_checkout()
    ensure_cloud_env(domain)
    write_runtime_files(domain, email)
    docker_build(no_cache=getattr(args, "no_cache", False))
    docker_up()
    seed_if_requested(getattr(args, "seed", False))
    docker_prune()
    cmd_status(args)
    ok("Updated and restarted.")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    compose(["ps"], check=False)
    compose(["exec", "-T", "app", "curl", "-fsS", f"http://127.0.0.1:{DEFAULT_GATEWAY_PORT}/health"], check=False)
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    aliases = {"gateway": "app", "api": "app", "nginx": "web", "caddy": "web"}
    service = aliases.get(args.service, args.service) if args.service else "app"
    return compose(["logs", "-f", "--tail", "200", service], check=False)


def cmd_rollback(args: argparse.Namespace) -> int:
    warn("Rollback restarts the currently built image. Re-deploy a previous checkout for a true code rollback.")
    compose(["restart"], check=False)
    return 0


def cmd_teardown(args: argparse.Namespace) -> int:
    cmd = ["down", "--remove-orphans"]
    if args.volumes:
        cmd.append("--volumes")
    compose(cmd, check=False)
    ok("Docker deployment stopped.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Vitrine cloud VM deploy (Docker + nginx)")
    ap.add_argument("--dry-run", action="store_true", help="print commands without running them")
    ap.add_argument("--app-dir", default=str(APP_DIR), help="where to sync/run the stack on the VM")
    ap.add_argument("--domain", default=DEFAULT_DOMAIN, help="public domain (TLS via Let's Encrypt)")
    ap.add_argument("--email", default="", help="ACME contact email (defaults to admin@<domain>)")
    ap.add_argument("--seed", action="store_true", help="force re-seed demo data after start")
    ap.add_argument("--no-cache", action="store_true", help="rebuild without Docker layer cache")
    # No subcommand => full deploy. That is the whole point of this file.
    ap.set_defaults(func=cmd_deploy)

    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("deploy", help="provision + build + start (default)")
    p.add_argument("--seed", action="store_true")
    p.add_argument("--no-cache", action="store_true")
    p.add_argument("--domain", default=DEFAULT_DOMAIN)
    p.add_argument("--email", default="")
    p.set_defaults(func=cmd_deploy)

    u = sub.add_parser("update", help="re-sync + rebuild + restart")
    u.add_argument("--seed", action="store_true")
    u.add_argument("--no-cache", action="store_true")
    u.add_argument("--domain", default=DEFAULT_DOMAIN)
    u.add_argument("--email", default="")
    u.set_defaults(func=cmd_update)

    sub.add_parser("status", help="show container + health status").set_defaults(func=cmd_status)

    lp = sub.add_parser("logs", help="tail logs (app|web)")
    lp.add_argument("service", nargs="?")
    lp.set_defaults(func=cmd_logs)

    sub.add_parser("rollback", help="restart the running image").set_defaults(func=cmd_rollback)

    td = sub.add_parser("teardown", help="stop the stack")
    td.add_argument("--volumes", action="store_true", help="also delete SQLite/files/cert volumes")
    td.set_defaults(func=cmd_teardown)

    return ap


def main(argv: list[str]) -> int:
    global DRY, APP_DIR
    args = build_parser().parse_args(argv)
    DRY = args.dry_run
    APP_DIR = Path(args.app_dir)
    if DRY:
        warn("DRY-RUN: no changes will be made.\n")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
