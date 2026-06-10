#!/usr/bin/env sh
set -eu

mkdir -p /data /app/files

# Seed the data volume from the database baked into the image on first boot.
# If /data already has a database (existing volume), leave it untouched.
if [ ! -f /data/vitrine.db ] && [ -f /app/seed/vitrine.db ]; then
    echo "* Seeding /data/vitrine.db from bundled database..."
    cp /app/seed/vitrine.db /data/vitrine.db
fi

# Make sure the schema is present (no-op when the seeded DB already has tables).
python -m backend.shared.db_setup --ensure

exec "$@"
