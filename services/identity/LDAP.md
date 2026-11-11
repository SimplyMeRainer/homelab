# FreeIPA → Keycloak native LDAP integration

After the official server role and public CA verification, create the explicitly
approved `management-users` IPA group and add only authorized people. The realm
LDAP filter requires direct `memberOf=cn=management-users,...`; nested membership
is not promised. Existing users need mail attributes for application onboarding.

A native LDAP-only account (not a Kerberos human/admin) supplies read-only binds.
Use the generated **separate** `ldap_bind_password`, without a trailing newline,
and the configured IPA base DN. Run only from a trusted administrator workstation
with OpenLDAP clients and the independently verified IPA CA. This is a one-time
privileged identity ceremony, not an automatic Directory Manager login:

```sh
umask 077
sh identity/bind-ldif.sh runtime/identity/keycloak-bind.ldif \
  runtime/secrets/ldap_bind_password dc=lab,dc=example
LDAPTLS_CACERT="$PWD/runtime/identity/ipa-ca.crt" ldapadd -x \
  -H ldaps://identity.lab.example:636 -D 'cn=Directory Manager' -W \
  -f runtime/identity/keycloak-bind.ldif
# -W prompts for the independent Directory Manager password. Never use -w.
```

The generated LDIF contains a base64 password (encoding is not encryption), is
mode0600 and must never be printed, logged or committed. Store encrypted if needed
for controlled recovery, otherwise securely remove it after successful enrollment.
Do not rerun `ldapadd` blindly if the DN exists; inspect its ownership and rotate
with a reviewed native `ldapmodify` change instead. The fixed password-expiration
attribute is an explicit long-lived system-account exception; schedule a bounded
rotation policy, monitor expiry, and update it before 2038. Never make this account
a member of `admins`, grant it Directory Manager rights or enable directory writes
from Keycloak. FreeIPA's native authenticated read ACLs provide the required
attributes; review custom ACLs if your server differs, rather than granting broad
write access.

Verify actual certificate checking and credential use without exposing a password:

```sh
LDAPTLS_CACERT="$PWD/runtime/identity/ipa-ca.crt" ldapsearch -x \
  -H ldaps://identity.lab.example:636 \
  -D 'uid=keycloak-bind,cn=sysaccounts,cn=etc,dc=lab,dc=example' \
  -y runtime/secrets/ldap_bind_password \
  -b 'cn=users,cn=accounts,dc=lab,dc=example' \
  '(memberOf=cn=management-users,cn=groups,cn=accounts,dc=lab,dc=example)' \
  uid mail givenName sn
```

This query prints directory attributes, not credentials: use it privately, never
save real identity outputs to this public repository. A successful LDAP search is
necessary but not sufficient: Keycloak must also successfully authenticate an
allowed human and deny a known-valid nonmember. Confirm the LDAP provider is
READ_ONLY, LDAPS URL hostname matches the IPA leaf, truststore is mounted, group
filter is exact, and all configured app callback URIs match your edited DNS.
No `trustAll`, insecure LDAP, disabled cert verification or default bind password
is provided. Keycloak realm changes after initial import require its native
Admin Console or authenticated Admin REST API, followed by read-back and a fresh
login test. Back up the actual PostgreSQL database, not only this import file.
