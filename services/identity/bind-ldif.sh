#!/bin/sh
# Generate a protected LDIF, not a deployment wrapper. Never log its contents.
set -eu
umask 077
out=${1:?usage: sh bind-ldif.sh NEW_LDIF_FILE SECRET_FILE BASE_DN}
secret=${2:?protected password file required}
base=${3:?IPA base DN required, e.g. dc=lab,dc=example}
case "$base" in *[!a-zA-Z0-9=,.-]*|'') echo 'invalid base DN' >&2; exit 2;; esac
[ ! -e "$out" ] && [ ! -L "$out" ] || { echo 'refusing to overwrite LDIF' >&2; exit 1; }
parent=$(dirname "$out")
[ -d "$parent" ] && [ ! -L "$parent" ] || { echo 'protected existing parent required' >&2; exit 1; }
permissions=$(LC_ALL=C ls -ld "$parent")
case "$permissions" in drwx------*) ;; *) echo 'LDIF parent must be mode 0700' >&2; exit 1;; esac
# Validate before opening output; POSIX pipelines only report the last status.
[ -f "$secret" ] && [ ! -L "$secret" ] && [ -r "$secret" ] && [ -s "$secret" ] || {
  echo 'secret must be a readable nonempty regular file' >&2; exit 1;
}
permissions=$(LC_ALL=C ls -ld "$secret")
case "$permissions" in -r--------*|-rw-------*) ;; *) echo 'secret must be owner-readable and protected' >&2; exit 1;; esac
encoded=$(base64 < "$secret")
encoded=$(printf '%s' "$encoded" | tr -d '\n')
[ -n "$encoded" ] || { echo 'empty encoded secret' >&2; exit 1; }
# Caller owns a protected existing parent; noclobber makes creation exclusive.
set -C
{
  printf 'dn: uid=keycloak-bind,cn=sysaccounts,cn=etc,%s\n' "$base"
  printf 'changetype: add\nobjectClass: account\nobjectClass: simpleSecurityObject\nuid: keycloak-bind\n'
  printf 'userPassword:: '
  printf '%s' "$encoded"
  printf '\npasswordExpirationTime: 20380119031407Z\nnsIdleTimeout: 0\n'
} > "$out" || exit 1
