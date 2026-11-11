# Management services: native Compose + FreeIPA

This source kit keeps management outside both Kubernetes clusters. It provisions
persistent Forgejo, MinIO, Vault, Keycloak/PostgreSQL, Prometheus, Grafana,
Alertmanager and n8n on one prepared Linux Docker host; the official FreeIPA
Ansible collection installs a separate prepared identity VM. This is a lab
baseline, **not an HA deployment or a production/security certification**.

**Validation boundary:** the offline tests exercise the real Compose parser,
OpenSSL CA/leaf generation, secret-file generation and negative safety cases.
FreeIPA collection 1.14.6 was fetched and the real playbook syntax checked.
The checksum-verified MinIO release source was actually cross-compiled with
Go 1.24.7 to a statically linked Linux/AMD64 ELF binary. This is **not a Dockerfile
build or a binary execution/startup test**. No daemon, container, Docker image
build, live LDAP login, SSO flow, restore or deployment was exercised.
Container-native `promtool`/`amtool`/Vault/Keycloak validation remains
operator qualification, not a claimed pass. These pinned releases need a current
vulnerability review before deployment; a digest is identity, not security approval.

**MinIO upstream blocker:** anonymous Docker Hub and Quay manifest retrieval
returned HTTP 401, including after registry token exchange. Rather than invent a
public digest, `minio/Dockerfile` builds the actual upstream release source whose
archive SHA-256 was fetched and computed, using verified digest-pinned Go/Alpine
bases. This is an explicit exception to public-image pinning: native source
cross-compilation succeeded, but the **Dockerfile build and server startup remain
unqualified**. Build on the approved host, scan it, publish to your controlled
registry and replace the local `image` with its resulting immutable digest for
repeatable deployment. Do not substitute an unreviewed third-party image.
`images.lock.json` records the eight service-image manifest digests, two build-base
digests, retrieval URLs and the MinIO source checksum. They identify manifest
indexes; platform-specific child manifests are selected by Docker.

## 1. Prerequisites and addresses

* Prepared Linux management host with Docker Engine + Compose, trusted admin
  access, sufficient persistent disk, OpenSSL, Python 3 + PyYAML, Apache
  `htpasswd` with bcrypt, and normal time synchronization. Do not deploy this kit
  by starting a desktop daemon. Reserve a real management IPv4 and firewall it
  to your administrator/client networks **including Docker's forwarding rules**.
* Prepared CentOS Stream 9 / RHEL 9 or Fedora 40+ identity guest, current supported
  FreeIPA packages, correct FQDN, forward/reverse DNS, time synchronization,
  package repositories and existing trusted SSH host keys. Use a maintained OS
  release supported by your FreeIPA package repositories. This is not an Ubuntu
  FreeIPA-server recipe; a generic Ubuntu baseline is insufficient.
* Make all `*.lab.example` service A records resolve to your edited management
  address and `identity.lab.example` to your edited identity guest. Host and
  containers must use DNS that resolves both; no public-first split-DNS failure.
  DNS and NTP are seed infrastructure, not services secretly provided by this kit.
* `192.0.2.40`, `192.0.2.41`, `lab.example` and all usernames here are fictional.
  Copy `management.env.example` to **ignored** `runtime/management.env`, edit every
  address/hostname/DN and use absolute paths for TLS_DIR, SECRET_DIR and
  IDENTITY_CA_FILE. The env file contains no passwords. Edit realm `lab` and
  corresponding URLs together if renaming it.

Run all commands below from `services/`. In shells define:

```sh
umask 077
mkdir -p runtime/identity runtime/backups
chmod 700 runtime runtime/identity runtime/backups
cp management.env.example runtime/management.env
# Edit runtime/management.env now. DO NOT deploy documentation addresses.
dc() { docker compose --env-file runtime/management.env -f compose.yaml "$@"; }
```

## 2. Install identity first with the official collection

Copy `identity/inventory.example.yml` to `runtime/identity/inventory.yml`, edit it,
and retain strict SSH host verification. Permit the normal FreeIPA HTTPS,
Kerberos, LDAP/LDAPS and time services only for appropriate management clients;
there is no DNS server installation in this inventory. Configure authoritative
DNS yourself before running the role. Do not enroll a host with an existing
conflicting identity deployment.

```sh
ansible-galaxy collection install -r identity/requirements.yml
ansible-vault create runtime/identity/passwords.vault.yml
# In the encrypted editor set independent ipaadmin_password and ipadm_password,
# each at least 16 characters; no defaults, and no plaintext file in Git.
ANSIBLE_CONFIG=identity/ansible.cfg ansible-playbook \
  -i runtime/identity/inventory.yml identity/install.yml --syntax-check
ANSIBLE_CONFIG=identity/ansible.cfg ansible-playbook \
  -i runtime/identity/inventory.yml identity/install.yml \
  -e @runtime/identity/passwords.vault.yml --ask-vault-pass --ask-become-pass
```

The role runs with `no_log`; do not enable Ansible debug/secret callback logging.
Confirm the identity guest's native `ipactl status`, `ipa ping`, a fresh Kerberos
login and both DNS directions. Export **only** the identity guest's public
`/etc/ipa/ca.crt` via your approved authenticated channel to
`runtime/identity/ipa-ca.crt`; check its fingerprint independently. This is the
IPA CA, not the management CA generated below. Keycloak mounts it read-only as
`/opt/keycloak/conf/truststores/ipa-ca.crt` and uses strict verified LDAPS.

Create the `management-users` group with native `ipa group-add management-users`
and explicitly add approved people with `ipa group-add-member management-users
--users=NAME`; do not add everyone by default. A dedicated LDAP-only system
account is described in `identity/LDAP.md`. Never use the Directory Manager or
IPA admin password as Keycloak's persistent bind credential.

## 3. Separate PKI, secret and runtime inputs

On a trusted offline/admin workstation, generate a **new** CA and eight distinct
hostname-SAN leaves (replace the suffix):

```sh
sh pki.sh runtime/pki-issued lab.example
sh secrets.sh runtime/secrets
```

The scripts refuse existing output directories, set umask 077, directories 0700
and files 0600, and never print secret values. PKI has a critical CA=true/pathlen=0
root with cert-sign/CRL-sign usage; leaves are CA=false/serverAuth with both their
configured FQDN and Compose-internal service DNS name. Leaf validity is 397 days.
If overriding individual hostnames rather than the suffix, issue matching SAN
leaves with your organizational CA; do not disable hostname verification.

Securely transfer only `ca.crt`, the eight leaf pairs and protected secrets to
the management host (`TLS_DIR` points at the leaf directory, normally
`runtime/pki`). **Keep `ca.key` off the host and out of every container and Git.**
Encrypt the offline CA key and secret backups with your approved offline store;
OpenSSL output is private but not itself encrypted at rest. Trust the public
management CA on client workstations after verifying its fingerprint.

Compose local file-backed secrets are read-only mounts, **not an encrypted
secret store**. Their `uid`/`mode` declarations cannot remap local source-file
ownership; set real Linux ownership before starting anything. Keep parent
runtime/TLS/secret directories 0700; the rootful Docker daemon can mount files
through those parents. Keep every private key and secret 0600, and make only the
public CA readable across container UIDs. No container needs the CA private key.
On the deployment host, after protected transfer (adjust paths if edited):

```sh
sudo chown 1000:1000 runtime/pki/forgejo.* runtime/pki/minio.* \
  runtime/pki/keycloak.* runtime/pki/n8n.*
sudo chown 100:1000 runtime/pki/vault.*
sudo chown 65534:65534 runtime/pki/prometheus.* runtime/pki/alertmanager.*
sudo chown 472:0 runtime/pki/grafana.*
sudo chmod 644 runtime/pki/ca.crt runtime/identity/ipa-ca.crt
sudo chown 1000:1000 runtime/secrets/postgres_password \
  runtime/secrets/keycloak_admin_password runtime/secrets/ldap_bind_password \
  runtime/secrets/grafana_oidc_secret runtime/secrets/forgejo_oidc_secret \
  runtime/secrets/forgejo_secret_key runtime/secrets/forgejo_internal_token \
  runtime/secrets/minio_root_user runtime/secrets/minio_root_password \
  runtime/secrets/n8n_encryption_key
sudo chown 472:0 runtime/secrets/grafana_admin_password \
  runtime/secrets/monitor_password_grafana
sudo chown 65534:65534 runtime/secrets/monitor_password runtime/secrets/monitor-web.yml
sudo chmod 600 runtime/secrets/* runtime/pki/*.key
```

`grafana_oidc_secret` is consumed by both Keycloak UID1000 and Grafana UID472;
use the generated separate Grafana-owned copy below. The generated
monitoring password already has a separate Grafana-owned copy for the same
reason. Never loosen a credential to 0644 to work around ownership.

```sh
sudo chown 472:0 runtime/secrets/grafana_oidc_secret_grafana
sudo chmod 600 runtime/secrets/grafana_oidc_secret_grafana
```

The MinIO root identity, Keycloak bootstrap admin, Grafana recovery admin,
PostgreSQL password, LDAP bind password, OAuth clients, Forgejo keys, monitoring
password and n8n encryption key are independent inputs. The monitoring pair and
Grafana-client pair are duplicate copies of the **same logical credential** for
different UIDs, not shared passwords between unrelated services. Keep these
copies synchronized on rotation. Database initialization passwords and Grafana
bootstrap passwords do not automatically rotate an existing database/admin.

## 4. Validate, build and deploy in order

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
# Requires Python PyYAML, Docker CLI/Compose and htpasswd, but NOT a daemon.
dc config --quiet
dc config --format json > runtime/rendered-compose.json
python3 validate.py runtime/rendered-compose.json --keys runtime/pki
# On the approved Linux host only, with its already-running daemon:
dc pull --ignore-buildable
dc build minio
# Initialize the new Vault audit volume owner once, without starting Vault:
dc run --rm --no-deps --user 0:0 --entrypoint sh vault \
  -c 'chown 100:1000 /vault/file /vault/audit; chmod 700 /vault/file /vault/audit'
dc up -d postgres
dc up -d keycloak
# Complete identity/LDAP.md BEFORE expecting directory authentication.
dc up -d vault forgejo minio prometheus alertmanager grafana
# Restrict initial n8n ingress to the operator until the owner is enrolled.
dc up -d n8n
```

No socket mounts, privileged containers, CI runner or Kubernetes dependency are
used. All host-published TCP ports bind to the required explicit BIND_ADDRESS;
PostgreSQL is internal-only. Container listeners accept their container network
interfaces; that does not change the restrictive host publication. Never replace
BIND_ADDRESS with `0.0.0.0` or `::`. The verifier rejects these and Vault dev mode.
Native Docker named volumes persist container recreation; never run `down -v` on
a deployment you intend to keep.

### Data and exact mounts

| Service | Persistent named volume → container path | Runtime/config inputs |
|---|---|---|
| Forgejo | forgejo-data → /var/lib/gitea; forgejo-config → /etc/gitea | environment-to-INI; file URI secret/internal token; TLS + public CA |
| MinIO | minio-data → /data | native root-user/password files; TLS public.crt/private.key under /run/minio-tls |
| Vault | vault-data → /vault/file; vault-audit → /vault/audit | vault/vault.hcl → /vault/config/vault.hcl; leaf + public CA |
| PostgreSQL | postgres-data → /var/lib/postgresql/data | native POSTGRES_PASSWORD_FILE; no published host port |
| Keycloak | state in PostgreSQL (no ephemeral embedded DB) | lab-realm.json → /opt/keycloak/data/import; IPA public CA truststore; leaf; secret files read by non-tracing shell |
| Prometheus | prometheus-data → /prometheus | prometheus.yml + rules.yml; /run/monitor-web.yml; TLS + CA; monitoring password_file |
| Grafana | grafana-data → /var/lib/grafana | provisioned datasource; native __FILE admin/OAuth inputs; TLS + CA |
| Alertmanager | alertmanager-data → /alertmanager | alertmanager.yml; /run/monitor-web.yml; TLS |
| n8n | n8n-data → /home/node/.n8n (SQLite/settings) | protected file → non-tracing entrypoint adapter → native encryption-key environment; TLS; interactive owner onboarding |

The Compose project is `homelab-management`; volume names are prefixed with
`homelab-management_`. Read `dc config` for all concrete paths. Files under
`runtime/` must remain ignored and never be included in source-only publishing.

## 5. Mandatory onboarding and actual SSO boundary

**Keycloak installation alone is not SSO.** `keycloak/lab-realm.json` implements
verified read-only FreeIPA LDAPS user federation, a group membership filter,
confidential Authorization Code clients, exact HTTPS redirect URIs, and a group
claim used to restrict Grafana to Viewer. Only IPA `management-users` may log in
through this LDAP provider. The hardcoded Grafana Viewer claim is issued to
**every identity admitted by that realm filter**, not a separate per-app IPA role
sync. Keep the realm's local user creation restricted; do not create local users
there casually, as the same client claim applies to them. IPA remains password
source; no directory password is imported or synchronized back.

Import happens on an empty realm only. `--import-realm` skips an existing realm;
changing the JSON later does **not** update a deployed realm. Use the native
Keycloak Admin Console or authenticated Admin REST API for reviewed updates and
read back their exact configuration. Log into the master realm as the one-time
`bootstrap-admin` using its protected generated password; create a named admin,
set MFA, and remove/disable the temporary bootstrap account. In the lab realm,
test LDAP connection and authentication, verify the exact group filter and trust
settings, and test an allowed user **and a valid-password nonmember denial**.

Grafana's OIDC settings and datasource are provisioned, with verified TLS and
strict Viewer mapping. Keep the local recovery account/MFA. Verify a fresh
browser login through Keycloak, confirm Viewer-only access, and prove nonmember
and administration denial before calling SSO operational.

Forgejo starts closed to public registration and Actions. Create its recovery
admin with the native CLI; capture its randomly generated credential to a
protected enrollment file, never a terminal/session log:

```sh
umask 077
dc exec -T --user 1000 forgejo forgejo \
  --config /var/lib/gitea/custom/conf/app.ini admin user create \
  --username local-recovery-admin --email recovery@lab.example --admin \
  --random-password > runtime/forgejo-enrollment.txt
```

Open that protected credential through your approved secure workflow, sign in,
rotate it and enable MFA; securely remove the enrollment file when recorded in
your password manager. In **Site Administration → Authentication Sources**, add
OAuth2 source name **keycloak**, provider **OpenID Connect**, client ID `forgejo`,
the generated `forgejo_oidc_secret`, discovery URL
`https://keycloak.lab.example:8443/realms/lab/.well-known/openid-configuration`,
and scopes `openid profile email`. The exact callback already provisioned is
`https://forgejo.lab.example:3000/user/oauth2/keycloak/callback`. Adapt edited
hostnames consistently. Keep public registration disabled: pre-create the
approved Forgejo account and use its native account settings to link the
Keycloak source. Test login and denial; this manual native source-enrollment
ceremony is required, **not silently assumed applied by Compose**.

MinIO root login is only for initial administration. Create narrowly scoped users
and bucket policies through its native Console/API; do not hand root credentials
to applications or reuse this single-host data disk as a sole backup copy.
There is no MinIO OIDC policy/role integration promised by this baseline.

n8n first start requires the operator's HTTPS owner-account setup. Keep its port
operator-only until complete, then enroll authorized users using its supported
native onboarding. The community deployment is **not represented as Keycloak
SSO-enabled**; enterprise SSO requires appropriate licensing/configuration and
is outside this baseline. n8n has no Docker socket, Execute Command/file nodes
are excluded, environment access is blocked, and no separate code-runner sandbox
is deployed. Workflows and imported nodes remain trusted-code inputs: this is
not a multi-tenant code-execution security boundary.

Prometheus/Alertmanager use generated bcrypt basic-auth configuration and TLS,
not pretend OIDC. The initial Alertmanager receiver deliberately retains alerts
in the authenticated UI only; no email/chat paging is configured or claimed.
Vault uses independent native operator authentication; no automatic Vault
LDAP/OIDC/Kubernetes auth or application secret provisioning is claimed.

## 6. Vault initialization/unseal: human security ceremony

Install the official Vault CLI on the trusted operator workstation. Use the
correct hostname, `VAULT_ADDR=https://vault.lab.example:8200` and
`VAULT_CACERT=/path/to/verified/management-ca.crt`. Never use `-tls-skip-verify`,
`VAULT_SKIP_VERIFY`, tracing, or raw init output in logs. Health is HTTP501 before
initialization, HTTP503 while sealed, HTTP200 when ready. The file backend is
single-node and is **not Raft**; raft snapshot commands are invalid here.

Prepare five independently controlled PGP public keys and the recovery custodian's
root-token public key. Confirm their fingerprints out of band. Then:

```sh
umask 077
vault operator init -key-shares=5 -key-threshold=3 \
  -pgp-keys=holder1.asc,holder2.asc,holder3.asc,holder4.asc,holder5.asc \
  -root-token-pgp-key=root-custodian.asc -format=json \
  > /protected/offline-store/vault-init-encrypted.json
# Output contains PGP-encrypted shares/token only; distribute to custodians.
vault operator unseal
vault operator unseal
vault operator unseal
# Each custodian decrypts their own share privately and enters the masked prompt.
vault login
# Enter the separately decrypted root token only at the hidden prompt.
vault audit enable file file_path=/vault/audit/audit.json
vault secrets enable -path=kv kv-v2
```

Configure least-privilege policies and a named human auth method using Vault's
native CLI/API, create/verify a limited recovery operator, verify audit events
and explicit policy denials, then revoke the initial root token. Do not revoke
it until replacement recovery access and enough unseal custodians are verified.
Do not print, commit or store unencrypted shares/root tokens on the management
host. Every Vault restart reseals it: three custodians must unseal again. Test a
throwaway KV round trip before/after a controlled restart with a scoped token;
never print its contents. Disk/audit failure can affect service; monitor capacity.

## 7. Native health and configuration qualification

Use edited hostnames and a verified public CA path (no TLS bypass):

```sh
dc ps
curl --cacert runtime/pki/ca.crt --fail https://forgejo.lab.example:3000/api/healthz
curl --cacert runtime/pki/ca.crt --fail https://minio.lab.example:9000/minio/health/ready
curl --cacert runtime/pki/ca.crt https://vault.lab.example:8200/v1/sys/health
curl --cacert runtime/pki/ca.crt --fail https://keycloak.lab.example:8443/realms/lab/.well-known/openid-configuration
curl --cacert runtime/pki/ca.crt --fail https://grafana.lab.example:3001/api/health
curl --cacert runtime/pki/ca.crt --fail https://n8n.lab.example:5678/healthz
# curl --user monitor prompts for its password; do not put the password in argv.
curl --cacert runtime/pki/ca.crt --user monitor --fail https://prometheus.lab.example:9090/-/ready
curl --cacert runtime/pki/ca.crt --user monitor --fail https://alertmanager.lab.example:9093/-/ready
dc exec -T postgres pg_isready -U keycloak -d keycloak
dc exec -T prometheus promtool check config /etc/prometheus/prometheus.yml
dc exec -T alertmanager amtool check-config /etc/alertmanager/alertmanager.yml
```

Keycloak's internal management port9000 is not published. Discovery success is
not LDAP/SSO proof; the allowed/denied browser tests above are mandatory. Check
`docker inspect` port bindings against your expected host IP and confirm a
non-management client cannot connect. Native binary/startup and real storage
checks above have **not been executed by the source-kit author**.

## 8. Backups and restore

Keep encrypted, versioned copies off the management host: source revision,
`runtime/management.env`, deployment image digests, TLS leaf keys/CA trust,
independent secrets, database/content data and FreeIPA recovery material. Keep
offline root CA/private unseal materials separately. Never upload these to Git,
CI artifacts or this repository's documentation. Test restores on an isolated
host with no conflicting DNS/IP, preserving exact versions before upgrades.

* **PostgreSQL/Keycloak:** `dc exec -T postgres pg_dump -U keycloak -d keycloak
  -Fc > runtime/backups/keycloak.dump` (umask077). Encrypt and move it off-host.
  Restore into a new empty matching PostgreSQL using `pg_restore -U keycloak
  -d keycloak --clean --if-exists`; keep Keycloak stopped while restoring. Restore
  its matching client/LDAP secrets too. Realm JSON export alone is not DB backup.
* **Vault file backend:** obtain an approved maintenance window, stop Vault,
  take a consistent protected filesystem/NAS snapshot of **both** vault-data
  and vault-audit, and restart/unseal. There is no native raft snapshot here.
  Restore those complete volumes with exact ownership while stopped, then
  unseal with the original custodians; a volume copy without shares is unusable.
  Audit logs may contain sensitive metadata; retain/encrypt them separately.
* **Forgejo:** stop Forgejo before a coherent snapshot of both its data and
  config volumes (SQLite, repositories, attachments and keys). Restore both to
  empty matching volumes while stopped, UID1000, then verify repository clone,
  attachment access and linked login. A repository-only copy loses application
  state. Do not copy a live SQLite file without its native backup transaction.
* **MinIO:** use the native S3 API/`mc mirror` to an independent approved target
  with least-privilege identities, plus protected user/policy/config exports.
  For full single-node point-in-time recovery stop it and snapshot the complete
  data volume including internal `.minio.sys`, preserving UID1000. Never edit
  internal metadata or assume bucket objects alone back up IAM configuration.
* **Grafana/n8n:** stop each before snapshotting its complete volume; SQLite must
  be consistent. Restore corresponding secrets, especially the n8n encryption
  key, or stored workflow credentials cannot be decrypted. Restore UID472 for
  Grafana, UID1000 for n8n. Test login and a harmless workflow with reviewed
  credentials before enabling external schedules/webhooks.
* **Prometheus/Alertmanager:** stop before complete volume snapshots; preserve
  rules/config and bcrypt/password inputs as well. Restore UID65534. TSDB is not
  a substitute for source-controlled alert/rule configuration.
* **FreeIPA:** on the identity guest run native `ipa-backup` as root under the
  vendor's backup requirements, encrypt/transfer the result independently and
  retain its original realm/CA/Directory Manager recovery inputs. Restore with
  `ipa-restore` on a compatible isolated identity VM following the vendor's
  exact-version procedure, then validate DNS, Kerberos, LDAP and membership.
  A VM clone alone is not a safe active replica or identity migration.

Named volumes are engine-managed. Inspect them with `docker volume inspect
homelab-management_vault-data` (and the corresponding names in the table), then
use your platform's protected snapshot/backup mechanism; do not guess Docker's
host data-root path. Never restore data into running containers. Backups,
custodian availability and restores are operator requirements, not verified
outcomes of offline configuration tests.

## Upstream references

* [Forgejo container installation/configuration](https://forgejo.org/docs/latest/admin/installation-docker/)
* [Forgejo config reference](https://forgejo.org/docs/latest/admin/config-cheat-sheet/)
* [MinIO upstream source release](https://github.com/minio/minio/tree/RELEASE.2025-09-07T16-13-09Z)
* [Vault file storage](https://developer.hashicorp.com/vault/docs/configuration/storage/filesystem)
* [Vault operator init](https://developer.hashicorp.com/vault/docs/commands/operator/init)
* [Keycloak server import](https://www.keycloak.org/server/importExport)
* [Keycloak administration/LDAP](https://www.keycloak.org/docs/latest/server_admin/index.html)
* [Official FreeIPA role, pinned version](https://github.com/freeipa/ansible-freeipa/blob/v1.14.6/roles/ipaserver/README.md)
* [Prometheus HTTPS/auth](https://prometheus.io/docs/guides/basic-auth/)
* [Grafana generic OAuth](https://grafana.com/docs/grafana/latest/setup-grafana/configure-security/configure-authentication/generic-oauth/)
* [n8n deployment environment](https://docs.n8n.io/hosting/configuration/environment-variables/deployment/)
