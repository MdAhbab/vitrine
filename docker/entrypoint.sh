#!/usr/bin/env sh
set -eu

mkdir -p /data /app/files

python -m backend.shared.db_setup --ensure

exec "$@"
