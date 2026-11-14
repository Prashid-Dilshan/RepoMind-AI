#!/bin/sh
set -e
# Platforms like Render mount volumes owned by root. Fix ownership, then drop to the unprivileged user.
if [ "$(id -u)" = "0" ]; then
  mkdir -p "$DATA_DIR"
  chown -R app:app "$DATA_DIR"
  exec gosu app "$@"
fi
exec "$@"
