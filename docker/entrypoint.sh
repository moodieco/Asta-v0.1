#!/bin/sh
# Container entrypoint.
#
# Render mounts a persistent disk root-owned, while the image's app user is
# `asta` (uid 10001). Without this step the first write to ASTA_DATA_DIR fails
# with EACCES — so take ownership of the mount, then drop privileges. When no
# disk is mounted the directory is just an image layer, and this is a no-op.
set -eu

DATA_DIR="${ASTA_DATA_DIR:-/var/data}"

if [ "$(id -u)" = "0" ]; then
  mkdir -p "$DATA_DIR"
  chown -R asta:asta "$DATA_DIR" 2>/dev/null || echo "[entrypoint] warning: could not chown $DATA_DIR"

  if command -v setpriv >/dev/null 2>&1 && setpriv --reuid=asta --regid=asta --init-groups true 2>/dev/null; then
    exec setpriv --reuid=asta --regid=asta --init-groups "$@"
  fi
  # Some minimal images ship no setpriv/runuser. Staying up as root is worse
  # than a failed deploy nobody can debug, so run and say so loudly.
  echo "[entrypoint] warning: no setpriv — refusing to drop privileges, running as root"
fi

exec "$@"
