#!/usr/bin/env bash
# SOFIA Trade backup/restore (Phase 7).
#
# Backups are taken with pg_dump -Fc so a restore can be selective and the
# archive is a single verifiable file. A SHA-256 sidecar is written next to it so
# a truncated or corrupted archive is detected before it is trusted.
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
DB_USER="${POSTGRES_USER:-sofia}"
DB_NAME="${POSTGRES_DB:-sofia}"
PGHOST="${PGHOST:-db}"
PGPORT="${PGPORT:-5432}"

usage() {
    cat <<'EOF'
Usage:
  backup.sh backup            create a timestamped archive + sha256
  backup.sh list              list available archives
  backup.sh restore <file>    restore an archive (destructive; confirms first)
EOF
}

require_pg() {
    command -v pg_dump >/dev/null || { echo "pg_dump not found" >&2; exit 1; }
}

cmd_backup() {
    require_pg
    mkdir -p "$BACKUP_DIR"
    local stamp file
    stamp="$(date -u +%Y%m%dT%H%M%SZ)"
    file="$BACKUP_DIR/sofia-$stamp.dump"
    echo "==> dumping $DB_NAME@$PGHOST to $file"
    PGPASSWORD="${POSTGRES_PASSWORD:-}" pg_dump \
        -h "$PGHOST" -p "$PGPORT" -U "$DB_USER" -d "$DB_NAME" -Fc -f "$file"
    sha256sum "$file" > "$file.sha256"
    echo "==> ok: $file"
    echo "    $(du -h "$file" | cut -f1)"
}

cmd_list() {
    [ -d "$BACKUP_DIR" ] || { echo "no backup dir at $BACKUP_DIR"; return 0; }
    ls -1 "$BACKUP_DIR"/*.dump 2>/dev/null || echo "no archives yet"
}

cmd_restore() {
    local file="${1:-}"
    [ -n "$file" ] || { usage; exit 2; }
    [ -f "$file" ] || { echo "no such archive: $file" >&2; exit 1; }

    if [ -f "$file.sha256" ]; then
        echo "==> verifying checksum"
        (cd "$(dirname "$file")" && sha256sum -c "$(basename "$file").sha256")
    else
        echo "WARNING: no .sha256 sidecar for $file; integrity unverified" >&2
    fi

    echo "This REPLACES the contents of $DB_NAME on $PGHOST."
    read -r -p "Type the database name to confirm: " confirm
    [ "$confirm" = "$DB_NAME" ] || { echo "aborted"; exit 1; }

    command -v pg_restore >/dev/null || { echo "pg_restore not found" >&2; exit 1; }
    echo "==> restoring"
    PGPASSWORD="${POSTGRES_PASSWORD:-}" pg_restore \
        -h "$PGHOST" -p "$PGPORT" -U "$DB_USER" -d "$DB_NAME" \
        --clean --if-exists --no-owner "$file"
    echo "==> done"
}

case "${1:-}" in
    backup) cmd_backup ;;
    list) cmd_list ;;
    restore) shift; cmd_restore "${1:-}" ;;
    *) usage; exit 2 ;;
esac