#!/bin/sh
# Generate separate new credentials locally; no stdout secrets, no overwrites.
set -eu
umask 077
out=${1:?usage: sh secrets.sh NEW_SECRET_DIRECTORY}
[ ! -e "$out" ] || { echo 'refusing existing secret directory' >&2; exit 1; }
command -v htpasswd >/dev/null || { echo 'Apache htpasswd with bcrypt support required' >&2; exit 1; }
mkdir -m 700 -p "$out"
for name in postgres_password keycloak_admin_password ldap_bind_password grafana_admin_password grafana_oidc_secret forgejo_oidc_secret forgejo_secret_key forgejo_internal_token minio_root_password n8n_encryption_key monitor_password; do
  value=$(openssl rand -hex 32)
  printf '%s' "$value" > "$out/$name"
  unset value
done
printf '%s' storage-admin > "$out/minio_root_user"
# -i reads the password from stdin, never exposes it as argv.
hash=$(htpasswd -niB -C 12 monitor < "$out/monitor_password")
hash=${hash#*:}
printf 'tls_server_config:\n  cert_file: /run/tls.crt\n  key_file: /run/tls.key\nbasic_auth_users:\n  monitor: "%s"\n' "$hash" > "$out/monitor-web.yml"
# Compose local secrets do not remap UIDs: one copy per distinct consumer UID.
cp "$out/monitor_password" "$out/monitor_password_grafana"
cp "$out/grafana_oidc_secret" "$out/grafana_oidc_secret_grafana"
chmod 600 "$out"/*
printf '%s\n' 'Separate credentials generated; encrypt and back up them before deployment.'
