#!/bin/sh
set -e

# Write htpasswd from environment variable (injected via Secret Manager)
if [ -n "$BASIC_AUTH_HTPASSWD" ]; then
  echo "$BASIC_AUTH_HTPASSWD" > /etc/nginx/.htpasswd
else
  echo "WARNING: BASIC_AUTH_HTPASSWD not set, creating default deny-all"
  echo "" > /etc/nginx/.htpasswd
fi

exec "$@"
