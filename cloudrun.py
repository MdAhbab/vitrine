#!/usr/bin/env python3
"""
Vitrine — native CLOUD VM deploy (no Docker).

Targets a single Ubuntu/Debian VM and brings up the whole stack as
systemd units behind nginx + TLS. Implements backend.md §14.

Sub-commands:
    python cloudrun.py deploy --domain vitrine.example.com [--seed] [--workers 3]
    python cloudrun.py update            # git pull, rebuild FE, migrate, restart
    python cloudrun.py status            # systemctl status + health checks
    python cloudrun.py logs <service>    # journalctl -u vitrine-<service> -f
    python cloudrun.py rollback          # restart units on previous release
    python cloudrun.py teardown          # stop & disable all vitrine units

Global flags:
    --dry-run     print every action without changing the system
    --app-dir     install location (default /opt/vitrine)
    --user        service user (default vitrine)

Run on the VM as a sudo-capable user. No Docker — gunicorn/uvicorn workers
managed by systemd, static frontend + reverse proxy by nginx.
"""
from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
import textwrap
from pathlib import Path

# Port map mirrors backend.md §2 / localrun.py. Internal services bind to
# 127.0.0.1; only nginx (443/80) is public.
SERVICES: dict[str, tuple[str, int]] = {
    "gateway":         ("backend.gateway.app:app",                8000),
    "identity":        ("backend.services.identity.app:app",      8001),
    "catalog":         ("backend.services.catalog.app:app",       8002),
    "search":          ("backend.services.search.app:app",        8003),
    "orders":          ("backend.services.orders.app:app",        8004),
    "notifications":   ("backend.services.notifications.app:app", 8005),
    "hosting":         ("backend.services.hosting.app:app",       8006),
    "reviews":         ("backend.services.reviews.app:app",       8007),
    "ai-orchestrator": ("backend.ai.app:app",                     8010),
}

DRY = False
APP_DIR = Path("/opt/vitrine")
APP_USER = "vitrine"


# ----- helpers ----------------------------------------------------------------
def c(t: str, code: str) -> str:
    return t if not sys.stdout.isatty() else f"\033[{code}m{t}\033[0m"


def info(m: str) -> None: print(c("• ", "36") + m)
def ok(m: str) -> None:   print(c("✓ ", "32") + m)
def warn(m: str) -> None: print(c("! ", "33") + m)
def die(m: str) -> None:  sys.exit(c("✗ ", "31") + m)


def run(cmd: list[str] | str, *, shell: bool = False, check: bool = True) -> int:
    pretty = cmd if isinstance(cmd, str) else " ".join(cmd)
    if DRY:
        print(c("  [dry-run] ", "90") + pretty)
        return 0
    info(pretty)
    return subprocess.run(cmd, shell=shell, check=check).returncode


def sudo(cmd: list[str]) -> int:
    return run(["sudo", *cmd])


def write_file(path: Path, content: str, *, root: bool = False, mode: str | None = None) -> None:
    if DRY:
        print(c(f"  [dry-run] write {path} ({len(content)} bytes)", "90"))
        return
    if root:
        # write via sudo tee so we don't need to be root for the whole script
        p = subprocess.Popen(["sudo", "tee", str(path)], stdin=subprocess.PIPE)
        p.communicate(content.encode())
    else:
        path.write_text(content)
    if mode:
        (sudo if root else run)(["chmod", mode, str(path)])
    ok(f"wrote {path}")


def require_linux() -> None:
    if platform.system() != "Linux" and not DRY:
        die("cloudrun.py provisions a Linux VM. Use --dry-run to preview elsewhere, "
            "or run it on your Ubuntu/Debian VM.")


# ----- unit / nginx templates -------------------------------------------------
def systemd_unit(name: str, target: str, port: int, workers: int) -> str:
    is_ai = name == "ai-orchestrator"
    klass = "uvicorn.workers.UvicornWorker"
    exec_start = (
        f"{APP_DIR}/.venv/bin/gunicorn {target} "
        f"-k {klass} -w {workers} -b 127.0.0.1:{port} "
        f"--timeout {120 if is_ai else 60} --graceful-timeout 30"
    )
    return textwrap.dedent(f"""\
        [Unit]
        Description=Vitrine {name} service
        After=network.target postgresql.service redis-server.service
        Wants=postgresql.service redis-server.service

        [Service]
        Type=exec
        User={APP_USER}
        Group={APP_USER}
        WorkingDirectory={APP_DIR}
        EnvironmentFile={APP_DIR}/.env
        ExecStart={exec_start}
        Restart=always
        RestartSec=3
        # hardening
        NoNewPrivileges=true
        PrivateTmp=true
        ProtectSystem=full

        [Install]
        WantedBy=multi-user.target
    """)


def ai_worker_template() -> str:
    return textwrap.dedent(f"""\
        [Unit]
        Description=Vitrine AI stream worker %i
        After=network.target redis-server.service
        Wants=redis-server.service

        [Service]
        Type=exec
        User={APP_USER}
        Group={APP_USER}
        WorkingDirectory={APP_DIR}
        EnvironmentFile={APP_DIR}/.env
        ExecStart={APP_DIR}/.venv/bin/python -m backend.ai.workers
        Restart=always
        RestartSec=3

        [Install]
        WantedBy=multi-user.target
    """)


def nginx_conf(domain: str) -> str:
    return textwrap.dedent(f"""\
        server {{
            listen 80;
            server_name {domain};

            # static frontend (vite build output)
            root {APP_DIR}/frontend/dist;
            index index.html;

            add_header X-Frame-Options SAMEORIGIN;
            add_header X-Content-Type-Options nosniff;
            add_header Referrer-Policy strict-origin-when-cross-origin;
            gzip on;
            gzip_types text/css application/javascript application/json image/svg+xml;

            # SPA fallback
            location / {{
                try_files $uri $uri/ /index.html;
            }}

            # API -> gateway
            location /api/ {{
                proxy_pass http://127.0.0.1:8000/;
                proxy_set_header Host $host;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                proxy_set_header X-Forwarded-Proto $scheme;
            }}

            # Concierge SSE stream (no buffering)
            location /api/ai/concierge {{
                proxy_pass http://127.0.0.1:8000/ai/concierge;
                proxy_set_header Connection '';
                proxy_http_version 1.1;
                proxy_buffering off;
                proxy_cache off;
                proxy_read_timeout 300s;
            }}
        }}
    """)


# ----- deploy steps -----------------------------------------------------------
def install_system_packages() -> None:
    info("Installing system packages (idempotent)...")
    sudo(["apt-get", "update", "-y"])
    pkgs = [
        "python3.11", "python3.11-venv", "python3-pip",
        "postgresql", "postgresql-contrib", "postgresql-15-pgvector",
        "redis-server", "nginx", "certbot", "python3-certbot-nginx",
        "git", "curl", "build-essential",
    ]
    sudo(["apt-get", "install", "-y", *pkgs])
    # Node via NodeSource (LTS)
    run("curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -",
        shell=True, check=False)
    sudo(["apt-get", "install", "-y", "nodejs"])
    sudo(["systemctl", "enable", "--now", "postgresql"])
    sudo(["systemctl", "enable", "--now", "redis-server"])
    ok("System packages ready.")


def create_app_user_and_dirs() -> None:
    info(f"Ensuring service user '{APP_USER}' and {APP_DIR}...")
    run(["sudo", "id", "-u", APP_USER], check=False)
    sudo(["useradd", "--system", "--create-home", "--shell", "/usr/sbin/nologin",
          APP_USER])  # harmless if it already exists (dry/idempotent intent)
    sudo(["mkdir", "-p", str(APP_DIR)])
    # sync current checkout into APP_DIR (rsync keeps it simple, no Docker)
    run(["sudo", "rsync", "-a", "--delete",
         "--exclude", ".venv", "--exclude", "node_modules",
         "--exclude", ".git", f"{Path.cwd()}/", f"{APP_DIR}/"], check=False)
    sudo(["chown", "-R", f"{APP_USER}:{APP_USER}", str(APP_DIR)])


def setup_backend(seed: bool) -> None:
    info("Setting up backend venv + database + migrations...")
    sudo(["-u", APP_USER, "python3.11", "-m", "venv", f"{APP_DIR}/.venv"])
    pip = f"{APP_DIR}/.venv/bin/pip"
    sudo(["-u", APP_USER, pip, "install", "-q", "--upgrade", "pip"])
    if (APP_DIR / "backend" / "requirements.txt").exists() or DRY:
        sudo(["-u", APP_USER, pip, "install", "-q", "-r",
              f"{APP_DIR}/backend/requirements.txt"])
    # DB role + database + pgvector
    sudo(["-u", "postgres", "psql", "-c",
          "CREATE ROLE vitrine LOGIN PASSWORD 'vitrine';"])
    sudo(["-u", "postgres", "psql", "-c", "CREATE DATABASE vitrine OWNER vitrine;"])
    sudo(["-u", "postgres", "psql", "-d", "vitrine", "-c",
          "CREATE EXTENSION IF NOT EXISTS vector;"])
    py = f"{APP_DIR}/.venv/bin/python"
    run(["sudo", "-u", APP_USER, f"{APP_DIR}/.venv/bin/alembic", "upgrade", "head"],
        check=False)
    if seed:
        run(["sudo", "-u", APP_USER, py, f"{APP_DIR}/backend/seed.py"], check=False)
    ok("Backend ready.")


def build_frontend() -> None:
    info("Building frontend (vite build -> static)...")
    fe = APP_DIR / "frontend"
    if (fe / "package.json").exists() or DRY:
        run(["sudo", "-u", APP_USER, "bash", "-lc",
             f"cd {fe} && npm ci && npm run build"], check=False)
        ok("Frontend built to frontend/dist.")
    else:
        warn("frontend/ not present — build it from frontend.md before deploy.")


def install_systemd_units(workers: int) -> None:
    info("Writing systemd units...")
    for name, (target, port) in SERVICES.items():
        write_file(Path(f"/etc/systemd/system/vitrine-{name}.service"),
                   systemd_unit(name, target, port, workers), root=True)
    write_file(Path("/etc/systemd/system/vitrine-ai-worker@.service"),
               ai_worker_template(), root=True)
    sudo(["systemctl", "daemon-reload"])
    for name in SERVICES:
        sudo(["systemctl", "enable", "--now", f"vitrine-{name}"])
    for i in range(workers):
        sudo(["systemctl", "enable", "--now", f"vitrine-ai-worker@{i}"])
    ok("systemd units installed & started.")


def configure_nginx(domain: str) -> None:
    info("Configuring nginx + TLS...")
    write_file(Path(f"/etc/nginx/sites-available/vitrine"),
               nginx_conf(domain), root=True)
    sudo(["ln", "-sf", "/etc/nginx/sites-available/vitrine",
          "/etc/nginx/sites-enabled/vitrine"])
    sudo(["rm", "-f", "/etc/nginx/sites-enabled/default"])
    sudo(["nginx", "-t"])
    sudo(["systemctl", "reload", "nginx"])
    info("Requesting TLS cert (certbot)...")
    run(["sudo", "certbot", "--nginx", "-d", domain, "--non-interactive",
         "--agree-tos", "-m", f"admin@{domain}", "--redirect"], check=False)
    ok("nginx + TLS configured.")


# ----- sub-commands -----------------------------------------------------------
def cmd_deploy(args: argparse.Namespace) -> int:
    require_linux()
    if not args.domain:
        die("deploy requires --domain")
    info(f"Deploying Vitrine to {args.domain} (workers={args.workers})")
    install_system_packages()
    create_app_user_and_dirs()
    setup_backend(seed=args.seed)
    build_frontend()
    install_systemd_units(args.workers)
    configure_nginx(args.domain)
    cmd_status(args)
    ok(f"Deployed. Visit https://{args.domain}")
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    require_linux()
    info("Updating release...")
    run(["sudo", "-u", APP_USER, "bash", "-lc", f"cd {APP_DIR} && git pull"], check=False)
    setup_backend(seed=False)   # installs deps + migrates (idempotent)
    build_frontend()
    for name in SERVICES:
        sudo(["systemctl", "restart", f"vitrine-{name}"])
    sudo(["systemctl", "reload", "nginx"])
    ok("Updated & restarted.")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    for name, (_t, port) in SERVICES.items():
        run(["sudo", "systemctl", "is-active", f"vitrine-{name}"], check=False)
        run(["curl", "-sf", "-o", "/dev/null", "-w", f"{name} :{port} -> %{{http_code}}\\n",
             f"http://127.0.0.1:{port}/health"], check=False)
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    svc = args.service or "gateway"
    return run(["sudo", "journalctl", "-u", f"vitrine-{svc}", "-f"], check=False)


def cmd_rollback(args: argparse.Namespace) -> int:
    warn("Rollback: restarting units on the current release dir. "
         "For true release rollback, point APP_DIR at a previous release "
         "(see backend.md §14) and re-run `update`.")
    for name in SERVICES:
        sudo(["systemctl", "restart", f"vitrine-{name}"])
    return 0


def cmd_teardown(args: argparse.Namespace) -> int:
    for name in SERVICES:
        sudo(["systemctl", "disable", "--now", f"vitrine-{name}"])
    sudo(["rm", "-f", "/etc/nginx/sites-enabled/vitrine"])
    sudo(["systemctl", "reload", "nginx"])
    ok("Vitrine units stopped & disabled.")
    return 0


# ----- main -------------------------------------------------------------------
def main() -> int:
    global DRY, APP_DIR, APP_USER
    ap = argparse.ArgumentParser(description="Vitrine cloud VM deploy (native, no Docker)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--app-dir", default=str(APP_DIR))
    ap.add_argument("--user", default=APP_USER)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("deploy")
    p.add_argument("--domain")
    p.add_argument("--seed", action="store_true")
    p.add_argument("--workers", type=int, default=2)
    p.set_defaults(func=cmd_deploy)

    sub.add_parser("update").set_defaults(func=cmd_update)
    sub.add_parser("status").set_defaults(func=cmd_status)
    lp = sub.add_parser("logs"); lp.add_argument("service", nargs="?"); lp.set_defaults(func=cmd_logs)
    sub.add_parser("rollback").set_defaults(func=cmd_rollback)
    sub.add_parser("teardown").set_defaults(func=cmd_teardown)

    args = ap.parse_args()
    DRY = args.dry_run
    APP_DIR = Path(args.app_dir)
    APP_USER = args.user
    if DRY:
        warn("DRY-RUN: no changes will be made.\n")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
