#!/usr/bin/env sh
set -eu

APP_UID=10001
APP_GID=10001

# ── phase 1: runs as root ──────────────────────────────────────────────────
# Volume mount points only exist once Docker has attached them, so ownership
# has to be fixed here rather than at build time. This also repairs volumes
# created by an older image that ran the app as root — without it, upgrading
# would leave the unprivileged app unable to write its own database.
if [ "$(id -u)" = "0" ]; then
    mkdir -p /data /app/files

    # Seed the data volume from the database baked into the image on first
    # boot. An existing volume is left untouched.
    if [ ! -f /data/vitrine.db ] && [ -f /app/seed/vitrine.db ]; then
        echo "* Seeding /data/vitrine.db from bundled database..."
        cp /app/seed/vitrine.db /data/vitrine.db
    fi

    chown -R "$APP_UID:$APP_GID" /data /app/files 2>/dev/null || true

    # Re-exec this script unprivileged. The app parses user-supplied READMEs,
    # accepts uploads and fetches user-supplied preview URLs; none of that
    # should run as root. If setpriv is unavailable we continue as root rather
    # than refuse to boot — a running site beats a hardened one that is down.
    if command -v setpriv >/dev/null 2>&1; then
        exec setpriv --reuid="$APP_UID" --regid="$APP_GID" --init-groups -- "$0" "$@"
    fi
    echo "! setpriv not found; continuing as root." >&2
fi

# ── phase 2: runs as the app user ──────────────────────────────────────────
# Creates any table the shipped database predates. Idempotent (create_all is
# checkfirst), and a no-op on an already-current schema. Must run after the
# privilege drop so the SQLite -wal/-shm sidecars belong to the app user.
python -m backend.shared.db_setup --ensure

exec "$@"
