#!/usr/bin/env python3
"""
Vitrine — native CLOUD VM deploy (no Docker).

Targets a single Ubuntu/Debian VM and brings up the whole stack as
systemd units behind Caddy/nginx + TLS. Implements backend.md §14.

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
managed by systemd, static frontend + reverse proxy by Caddy/nginx.
"""
from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
import textwrap
from pathlib import Path

SERVICE_TARGETS: dict[str, str] = {
    "gateway": "backend.gateway.app:app",
    "identity": "backend.services.identity.app:app",
    "catalog": "backend.services.catalog.app:app",
    "search": "backend.services.search.app:app",
    "orders": "backend.services.orders.app:app",
    "notifications": "backend.services.notifications.app:app",
    "hosting": "backend.services.hosting.app:app",
    "reviews": "backend.services.reviews.app:app",
    "chats": "backend.services.chats.app:app",
    "ai-orchestrator": "backend.ai.app:app",
}

SERVICES: dict[str, tuple[str, int]] = {}
PROXY = "caddy"
DEFAULT_GATEWAY_PORT = 18000

DRY = False
APP_DIR = Path("/opt/vitrine")
APP_USER = "vitrine"


def build_services(gateway_port: int) -> dict[str, tuple[str, int]]:
    ports = {
        "gateway": gateway_port,
        "identity": gateway_port + 1,
        "catalog": gateway_port + 2,
        "search": gateway_port + 3,
        "orders": gateway_port + 4,
        "notifications": gateway_port + 5,
        "hosting": gateway_port + 6,
        "reviews": gateway_port + 7,
        "chats": gateway_port + 8,
        "ai-orchestrator": gateway_port + 10,
    }
    return {name: (target, ports[name]) for name, target in SERVICE_TARGETS.items()}


# ----- helpers ----------------------------------------------------------------
def c(t: str, code: str) -> str:
    return t if not sys.stdout.isatty() else f"\033[{code}m{t}\033[0m"


def info(m: str) -> None: print(c("• ", "36") + m)
def ok(m: str) -> None:   print(c("✓ ", "32") + m)
def warn(m: str) -> None: print(c("! ", "33") + m)
def die(m: str) -> None:  sys.exit(c("✗ ", "31") + m)


def run(
    cmd: list[str] | str,
    *,
    shell: bool = False,
    check: bool = True,
    timeout: int | None = None,
) -> int:
    pretty = cmd if isinstance(cmd, str) else " ".join(cmd)
    if DRY:
        print(c("  [dry-run] ", "90") + pretty)
        return 0
    info(pretty)
    try:
        return subprocess.run(cmd, shell=shell, check=check, timeout=timeout).returncode
    except subprocess.TimeoutExpired:
        die(f"Command timed out after {timeout}s: {pretty}")
        return 1  # unreachable but satisfies type checker


def sudo(cmd: list[str], *, check: bool = True, timeout: int | None = None) -> int:
    return run(["sudo", *cmd], check=check, timeout=timeout)


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


def write_file_as_user(path: Path, content: str, user: str) -> None:
    if DRY:
        print(c(f"  [dry-run] write {path} as {user} ({len(content)} bytes)", "90"))
        return
    p = subprocess.Popen(["sudo", "-u", user, "tee", str(path)], stdin=subprocess.PIPE)
    p.communicate(content.encode())
    ok(f"wrote {path} as {user}")


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


def nginx_conf(domain: str, gateway_port: int) -> str:
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
                proxy_pass http://127.0.0.1:{gateway_port}/;
                proxy_set_header Host $host;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                proxy_set_header X-Forwarded-Proto $scheme;
            }}

            # Concierge SSE stream (no buffering)
            location /api/ai/concierge {{
                proxy_pass http://127.0.0.1:{gateway_port}/ai/concierge;
                proxy_set_header Connection '';
                proxy_http_version 1.1;
                proxy_buffering off;
                proxy_cache off;
                proxy_read_timeout 300s;
            }}
        }}
    """)


def caddy_conf(domain: str, gateway_port: int) -> str:
    return textwrap.dedent(f"""\
        {{
            email admin@{domain}
        }}

        {domain} {{
            root * {APP_DIR}/frontend/dist
            encode zstd gzip

            header {{
                X-Frame-Options "SAMEORIGIN"
                X-Content-Type-Options "nosniff"
                Referrer-Policy "strict-origin-when-cross-origin"
            }}

            handle_path /api/* {{
                reverse_proxy 127.0.0.1:{gateway_port} {{
                    flush_interval -1
                    header_up X-Real-IP {{remote_host}}
                    header_up X-Forwarded-For {{remote_host}}
                    header_up X-Forwarded-Proto {{scheme}}
                }}
            }}

            try_files {{path}} /index.html
            file_server
        }}
    """)


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text().splitlines():
        if not raw or raw.strip().startswith("#") or "=" not in raw:
            continue
        k, v = raw.split("=", 1)
        values[k.strip()] = v.strip()
    return values


def upsert_env(path: Path, key: str, value: str) -> None:
    lines = path.read_text().splitlines() if path.exists() else []
    replaced = False
    out: list[str] = []
    for raw in lines:
        line = raw.strip()
        if line.startswith(f"{key}="):
            out.append(f"{key}={value}")
            replaced = True
        else:
            out.append(raw)
    if not replaced:
        out.append(f"{key}={value}")
    write_file_as_user(path, "\n".join(out).rstrip() + "\n", APP_USER)


def robots_txt(domain: str) -> str:
    return textwrap.dedent(f"""\
        User-agent: *
        Allow: /

        Disallow: /#/admin-login
        Disallow: /#/dashboard

        Sitemap: https://{domain}/sitemap.xml
    """)


def sitemap_xml(domain: str) -> str:
    urls = [
        "/",
        "/#/browse",
        "/#/sell",
        "/#/pricing",
        "/#/terms",
        "/#/privacy",
        "/#/disclaimer",
    ]
    body = "\n".join(
        f"  <url>\n    <loc>https://{domain}{u}</loc>\n  </url>" for u in urls
    )
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}\n</urlset>\n'


def write_public_assets(domain: str) -> None:
    public_dir = APP_DIR / "frontend" / "public"
    dist_dir = APP_DIR / "frontend" / "dist"
    if not DRY:
        sudo(["-u", APP_USER, "mkdir", "-p", str(public_dir)], check=False)
    write_file_as_user(public_dir / "robots.txt", robots_txt(domain), APP_USER)
    write_file_as_user(public_dir / "sitemap.xml", sitemap_xml(domain), APP_USER)
    write_file_as_user(public_dir / "ads.txt", "google.com, pub-9972634875622184, DIRECT, f08c47fec0942fa0\n", APP_USER)
    if dist_dir.exists() or DRY:
        if not DRY:
            sudo(["-u", APP_USER, "mkdir", "-p", str(dist_dir)], check=False)
        write_file_as_user(dist_dir / "robots.txt", robots_txt(domain), APP_USER)
        write_file_as_user(dist_dir / "sitemap.xml", sitemap_xml(domain), APP_USER)
        write_file_as_user(dist_dir / "ads.txt", "google.com, pub-9972634875622184, DIRECT, f08c47fec0942fa0\n", APP_USER)


# ----- deploy steps -----------------------------------------------------------
def install_system_packages() -> None:
    info("Installing system packages (idempotent)...")
    sudo(["apt-get", "update", "-y"])
    pkgs = [
        "python3", "python3-venv", "python3-pip",
        "postgresql", "postgresql-contrib", "postgresql-18-pgvector",
        "redis-server", "caddy", "nginx", "certbot", "python3-certbot-nginx",
        "git", "curl", "build-essential", "rsync",
    ]
    sudo(["apt-get", "install", "-y", *pkgs])
    # Node via NodeSource (LTS)
    run("curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -",
        shell=True, check=False)
    sudo(["apt-get", "install", "-y", "nodejs"])
    sudo(["systemctl", "enable", "--now", "postgresql"])
    sudo(["systemctl", "enable", "--now", "redis-server"])
    if PROXY == "caddy":
        sudo(["systemctl", "enable", "--now", "caddy"])
    else:
        sudo(["systemctl", "enable", "--now", "nginx"])
    ok("System packages ready.")


def create_app_user_and_dirs() -> None:
    info(f"Ensuring service user '{APP_USER}' and {APP_DIR}...")
    run(["sudo", "id", "-u", APP_USER], check=False)
    sudo(["useradd", "--system", "--create-home", "--shell", "/usr/sbin/nologin",
          APP_USER], check=False)
    sudo(["mkdir", "-p", str(APP_DIR)])
    # sync current checkout into APP_DIR (rsync keeps it simple, no Docker)
    run(["sudo", "rsync", "-a", "--delete",
         "--exclude", ".venv", "--exclude", "node_modules",
         "--exclude", ".git", f"{Path.cwd()}/", f"{APP_DIR}/"], check=False)
    sudo(["chown", "-R", f"{APP_USER}:{APP_USER}", str(APP_DIR)])


def ensure_runtime_env(domain: str) -> None:
    env_path = APP_DIR / ".env"
    if not env_path.exists() and (APP_DIR / ".env.example").exists():
        run(["sudo", "cp", str(APP_DIR / ".env.example"), str(env_path)])
        sudo(["chown", f"{APP_USER}:{APP_USER}", str(env_path)])
    upsert_env(env_path, "ENV", "prod")
    upsert_env(env_path, "FRONTEND_ORIGIN", f"https://{domain}")
    upsert_env(env_path, "PUBLIC_DOMAIN", domain)


def setup_backend(seed: bool) -> None:
    info("Setting up backend venv + database + migrations...")
    sudo(["-u", APP_USER, "python3", "-m", "venv", f"{APP_DIR}/.venv"])
    pip = f"{APP_DIR}/.venv/bin/pip"

    # Upgrade pip first (visible output, 120 s max)
    sudo(["-u", APP_USER, pip, "install", "--upgrade", "pip"],
         timeout=120)

    # tiktoken requires Rust/cargo to build its C extension.
    # Use system-wide apt install so cargo is on PATH for ALL subprocesses
    # (rustup installs per-user and pip's build env can't find it).
    cargo_check = subprocess.run(
        ["which", "cargo"], capture_output=True,
    )
    if cargo_check.returncode != 0:
        info("Rust/cargo not found — installing system-wide via apt...")
        sudo(["apt-get", "install", "-y", "rustc", "cargo"], timeout=300)

    if (APP_DIR / "backend" / "requirements.txt").exists() or DRY:
        info("Installing Python dependencies (this may take several minutes)...")
        # Explicitly inject cargo paths so pip build subprocesses find the compiler.
        # Covers both system cargo (/usr/bin) and any rustup install (~/.cargo/bin).
        cargo_bin = f"/home/{APP_USER}/.cargo/bin"
        pip_env = f"PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 PATH={cargo_bin}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        sudo(["-u", APP_USER, "bash", "-lc",
              f"{pip_env} {pip} install -r {APP_DIR}/backend/requirements.txt"],
             timeout=900)

    # DB role + database + pgvector (only if using Postgres)
    env_vars = _read_env(APP_DIR / ".env")
    db_url = env_vars.get("DATABASE_URL", "")
    if "postgresql" in db_url:
        sudo(["-u", "postgres", "psql", "-c",
              "CREATE ROLE vitrine LOGIN PASSWORD 'vitrine';"], check=False)
        sudo(["-u", "postgres", "psql", "-c", "CREATE DATABASE vitrine OWNER vitrine;"], check=False)
        sudo(["-u", "postgres", "psql", "-d", "vitrine", "-c",
              "CREATE EXTENSION IF NOT EXISTS vector;"], check=False)
    py = f"{APP_DIR}/.venv/bin/python"
    run(["sudo", "-u", APP_USER, f"{APP_DIR}/.venv/bin/alembic", "upgrade", "head"],
        check=False)
    if seed:
        run(["sudo", "-u", APP_USER, py, f"{APP_DIR}/backend/seed.py"], check=False)
    ok("Backend ready.")


def build_frontend(domain: str) -> None:
    info("Building frontend (vite build -> static)...")
    fe = APP_DIR / "frontend"
    write_public_assets(domain)
    if (fe / "package.json").exists() or DRY:
        run(["sudo", "-u", APP_USER, "bash", "-lc",
             f"cd {fe} && npm ci && npm run build"], check=False)
        write_public_assets(domain)
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


def configure_nginx(domain: str, gateway_port: int) -> None:
    info("Configuring nginx + TLS...")
    write_file(Path(f"/etc/nginx/sites-available/vitrine"),
               nginx_conf(domain, gateway_port), root=True)
    sudo(["ln", "-sf", "/etc/nginx/sites-available/vitrine",
          "/etc/nginx/sites-enabled/vitrine"])
    sudo(["rm", "-f", "/etc/nginx/sites-enabled/default"])
    sudo(["nginx", "-t"])
    sudo(["systemctl", "reload", "nginx"])
    info("Requesting TLS cert (certbot)...")
    run(["sudo", "certbot", "--nginx", "-d", domain, "--non-interactive",
         "--agree-tos", "-m", f"admin@{domain}", "--redirect"], check=False)
    ok("nginx + TLS configured.")


def configure_caddy(domain: str, gateway_port: int) -> None:
    info("Configuring Caddy + TLS...")
    write_file(Path("/etc/caddy/Caddyfile"), caddy_conf(domain, gateway_port), root=True)
    sudo(["systemctl", "reload", "caddy"], check=False)
    ok("Caddy configured.")


def configure_proxy(domain: str, gateway_port: int) -> None:
    if PROXY == "caddy":
        configure_caddy(domain, gateway_port)
    else:
        configure_nginx(domain, gateway_port)


# ----- sub-commands -----------------------------------------------------------
def cmd_deploy(args: argparse.Namespace) -> int:
    require_linux()
    if not args.domain:
        die("deploy requires --domain")
    info(f"Deploying Vitrine to {args.domain} (workers={args.workers})")
    install_system_packages()
    create_app_user_and_dirs()
    ensure_runtime_env(args.domain)
    setup_backend(seed=args.seed)
    build_frontend(args.domain)
    install_systemd_units(args.workers)
    configure_proxy(args.domain, SERVICES["gateway"][1])
    cmd_status(args)
    ok(f"Deployed. Visit https://{args.domain}")
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    require_linux()
    info("Updating release...")
    env_vars = _read_env(APP_DIR / ".env")
    domain = args.domain or env_vars.get("PUBLIC_DOMAIN") or env_vars.get("FRONTEND_ORIGIN", "").replace("https://", "")
    if not domain:
        warn("No domain found in .env (PUBLIC_DOMAIN/FRONTEND_ORIGIN). Using localhost for SEO assets.")
        domain = "localhost"
    run(["sudo", "-u", APP_USER, "bash", "-lc", f"cd {APP_DIR} && git pull"], check=False)
    ensure_runtime_env(domain)
    setup_backend(seed=False)   # installs deps + migrates (idempotent)
    build_frontend(domain)
    for name in SERVICES:
        sudo(["systemctl", "restart", f"vitrine-{name}"])
    if PROXY == "caddy":
        configure_caddy(domain, SERVICES["gateway"][1])
    else:
        configure_nginx(domain, SERVICES["gateway"][1])
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
    if PROXY == "caddy":
        sudo(["systemctl", "restart", "caddy"], check=False)
    else:
        sudo(["rm", "-f", "/etc/nginx/sites-enabled/vitrine"])
        sudo(["systemctl", "reload", "nginx"], check=False)
    ok("Vitrine units stopped & disabled.")
    return 0


# ----- main -------------------------------------------------------------------
def main() -> int:
    global DRY, APP_DIR, APP_USER, SERVICES, PROXY
    ap = argparse.ArgumentParser(description="Vitrine cloud VM deploy (native, no Docker)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--app-dir", default=str(APP_DIR))
    ap.add_argument("--user", default=APP_USER)
    ap.add_argument("--proxy", choices=["caddy", "nginx"], default="caddy")
    ap.add_argument("--gateway-port", type=int, default=DEFAULT_GATEWAY_PORT)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("deploy")
    p.add_argument("--domain")
    p.add_argument("--seed", action="store_true")
    p.add_argument("--workers", type=int, default=2)
    p.set_defaults(func=cmd_deploy)

    u = sub.add_parser("update")
    u.add_argument("--domain")
    u.set_defaults(func=cmd_update)
    sub.add_parser("status").set_defaults(func=cmd_status)
    lp = sub.add_parser("logs"); lp.add_argument("service", nargs="?"); lp.set_defaults(func=cmd_logs)
    sub.add_parser("rollback").set_defaults(func=cmd_rollback)
    sub.add_parser("teardown").set_defaults(func=cmd_teardown)

    args = ap.parse_args()
    DRY = args.dry_run
    APP_DIR = Path(args.app_dir)
    APP_USER = args.user
    PROXY = args.proxy
    SERVICES = build_services(args.gateway_port)
    if DRY:
        warn("DRY-RUN: no changes will be made.\n")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
