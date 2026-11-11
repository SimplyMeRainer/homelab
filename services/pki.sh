#!/bin/sh
# Offline CA and distinct DNS/SAN leaves; NEVER run with shell tracing.
set -eu
umask 077
out=${1:?usage: sh pki.sh NEW_OUTPUT_DIRECTORY DNS_SUFFIX}
domain=${2:?DNS suffix required}
case "$domain" in ''|*[!a-zA-Z0-9.-]*|.*|*..*|-*) echo 'invalid DNS suffix' >&2; exit 2;; esac
[ ! -e "$out" ] || { echo 'refusing to overwrite existing PKI directory' >&2; exit 1; }
mkdir -m 700 -p "$out"
cat > "$out/ca.cnf" <<EOF
[req]
prompt = no
distinguished_name = dn
x509_extensions = ca
[dn]
CN = $domain Management Offline Root
[ca]
basicConstraints = critical,CA:true,pathlen:0
keyUsage = critical,keyCertSign,cRLSign
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always
EOF
openssl genrsa -out "$out/ca.key" 4096 2>/dev/null
openssl req -new -x509 -sha256 -days 3650 -key "$out/ca.key" -out "$out/ca.crt" -config "$out/ca.cnf"
for name in forgejo minio vault keycloak prometheus grafana alertmanager n8n; do
  cat > "$out/$name.cnf" <<EOF
[req]
prompt = no
distinguished_name = dn
req_extensions = server
[dn]
CN = $name.$domain
[server]
basicConstraints = critical,CA:false
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = DNS:$name.$domain,DNS:$name
subjectKeyIdentifier = hash
EOF
  openssl genrsa -out "$out/$name.key" 2048 2>/dev/null
  openssl req -new -sha256 -key "$out/$name.key" -out "$out/$name.csr" -config "$out/$name.cnf"
  serial=$(openssl rand -hex 16)
  openssl x509 -req -sha256 -days 397 -in "$out/$name.csr" -CA "$out/ca.crt" -CAkey "$out/ca.key" -set_serial "0x$serial" -extfile "$out/$name.cnf" -extensions server -out "$out/$name.crt" 2>/dev/null
  openssl verify -CAfile "$out/ca.crt" "$out/$name.crt" >/dev/null
  rm "$out/$name.csr" "$out/$name.cnf"
done
rm "$out/ca.cnf"
chmod 600 "$out"/*
# On the deployment host transfer ONLY leaf files + public ca.crt, NOT ca.key.
# Re-own leaf keys to their container UIDs as documented before starting services.
printf '%s\n' 'PKI generated. Keep ca.key offline; transfer public CA and leaf pairs securely.'
