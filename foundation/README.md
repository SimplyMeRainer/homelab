# OpenStack / external-Ceph foundation

Native Ansible configuration producers and host/Ceph playbooks, followed by native
Kolla-Ansible. **Source implemented and offline exercised; NOT clean-room deployed.** Nothing here
has connected to a lab, installed software on a host, prepared a disk, or deployed
OpenStack during development.

## Explicit upstream Ceph SSH trust boundary

The pinned Ceph **19.2.7** manager implementation
[`src/pybind/mgr/cephadm/ssh.py`, lines 174–176](https://github.com/ceph/ceph/blob/v19.2.7/src/pybind/mgr/cephadm/ssh.py#L174-L176)
passes `known_hosts=None` directly to AsyncSSH. Its default SSH config also disables
host-key checking. Merely supplying `StrictHostKeyChecking yes` does not override
that Python argument. `ceph.yml` refuses locally unless the operator explicitly sets
`foundation_operator_accepts_cephadm_ssh_trust_model: true` (default **false**).
This is acceptance of native cephadm's trust model, NOT strict-host proof or an
attestation of an upstream fix. No ineffective SSH override is shipped.

Accept only on a dedicated isolated trusted management network: restrict switch
ports/VLAN membership to approved nodes, prohibit tenant/public access, firewall
management SSH to operator and cluster nodes, protect DNS/IP assignments and
routing against spoofing, and independently authenticate initial host identities.
If isolation cannot be established, do not accept or deploy. Protect the native
Ceph private enrollment key and privileged management hosts. Native cephadm does
not detect a substituted SSH endpoint; network trust is a real residual risk.
Ordinary Ansible retains strict host-key checking; TLS verification is unchanged.
Bootstrap, selected-empty-OSD and client creation approvals remain independent.

## Seed requirements (not produced by this directory)

* Five prepared Ubuntu 24.04 hosts with unique short names matching `node01` etc.
  All five are compute + Ceph; first three also control, first two also network.
  Edit the roles/list to change placement. The complete upstream 22.2.0 inventory
  service-group hierarchy is retained, not replaced by a toy inventory.
* Trusted admin SSH with independently authenticated known-host entries for both
  names and management IPs, passwordless sudo, Python 3 and working hostname/DNS,
  synchronized NTP, connectivity/MTU, adequate storage/RAM and virtualization.
  No OS imaging, host-key discovery-as-trust, credential retrieval or fencing.
* Management NIC already configured. Separate provider NIC must be unnumbered,
  not a VLAN child, and connected to the selected VLAN trunk. The raw NIC goes
  to br-ex; Neutron ML2 applies the provider VLAN **once**. No switch programming
  or host-network rewiring is attempted here.
* Explicit operator-selected **empty whole disks** under `/dev/disk/by-id/`.
  Remove placeholders. `preflight.yml` reads lsblk and rejects filesystems,
  partitions, children and mounts. Ceph additionally refuses unavailable devices.
  No all-disks specification, erase, wipe, formatting, or recovery cleanup exists.
* Operator CA/trust enrollment: issue API and backend certificates with correct
  DNS/IP SANs; trust the CA on the operator OS. Place private runtime files listed
  below. Production PKI issuance and recovery are human security ceremonies,
  not self-signed production TLS or verification bypasses.

All addresses/domain/device IDs are fictional editable seeds. RFC 5737 examples
are intentionally not routable. Do not deploy the example unchanged.

## Public dependency pins and provenance

* `requirements.txt`: Kolla-Ansible **22.2.0**, ansible-core **2.20.11**, Python 3.12.
  [OpenStack Gazpacho releases](https://releases.openstack.org/gazpacho/)
  identifies release 22.2.0 / commit `a3badc9325e53d875b30f3b89947e7e2e2863781`.
  Its requirements allow core >=2.19, !=2.19.0, <2.21. Do not use global 2.21
  for deployment; it may still parse these small local playbooks.
* `requirements.yml`: public `ansible-collection-kolla` tag **9.2.0**, installed
  successfully in an isolated development environment. That repository's Galaxy
  metadata reports collection version 1.0.0; the source tag is the effective pin.
* `versions.yml`: Ceph **19.2.7** cephadm archive with retrieved SHA-256, and the
  retrieved Quay multiarchitecture manifest digest for `ceph:v19.2.7`. See
  [Ceph release index](https://docs.ceph.com/en/latest/releases/) and
  [archive](https://download.ceph.com/rpm-19.2.7/el9/noarch/cephadm).
* OpenStack containers use native Kolla **2026.1** series tags. These are **not**
  per-service immutable digest locks. A fully reproducible image registry/BOM is
  a remaining qualification gap; do not equate the CLI pin with every image pin.

## Exact local setup and render commands

Run from the repository root; substitute a Python 3.12 interpreter if necessary.
These commands install dependencies only into ignored runtime state:

```bash
umask 077
export REPO="$PWD"
export RUNTIME="$REPO/runtime/foundation"
mkdir -p config/local "$RUNTIME"
chmod 700 config/local "$RUNTIME"
cp foundation/vars.example.yml config/local/foundation.yml
# Edit config/local/foundation.yml. Leave deployment opt-ins false for rendering.
uv venv "$RUNTIME/venv" --python 3.12
uv pip install --python "$RUNTIME/venv/bin/python" -r foundation/requirements.txt
. "$RUNTIME/venv/bin/activate"
export ANSIBLE_CONFIG="$REPO/foundation/ansible.cfg"
export ANSIBLE_COLLECTIONS_PATH="$RUNTIME/collections"
ansible-galaxy collection install -r foundation/requirements.yml -p "$ANSIBLE_COLLECTIONS_PATH"
ansible-playbook -i localhost, -c local foundation/render.yml   -e @config/local/foundation.yml -e foundation_runtime="$RUNTIME"
ansible-inventory -i "$RUNTIME/inventory.ini" --graph
```

`foundation_runtime` must be absolute and remain outside committed source. Render
is local and does not require reviewed/live seeds. Generated directories are
0700 and configuration files 0600. It produces:

| Output beneath `$RUNTIME` | Consumer |
| --- | --- |
| `inventory.ini` | Full native Kolla inventory and Ansible Ceph groups |
| `host-inputs.yml` | Explicit per-host disk lists consumed with `-e @...` |
| `kolla/globals.yml` | Kolla release, topology, TLS and external-Ceph variables |
| `kolla/config/neutron/ml2_conf.ini` | Native bounded provider VLAN override |
| `kolla-commands.sh` | Gated bootstrap/prechecks/deploy/post-deploy sequence |
| `ceph/fsid` | Generated native cluster identity after approved Ceph health |

## Read-only preflight and approved execution order

The following are **operator execution instructions, not actions performed during
development**. Set `foundation_inputs_reviewed: true` only after editing/reviewing
all seeds. Never use `--limit` to omit the local safety play or skip safety tasks.

```bash
ansible-playbook -i "$RUNTIME/inventory.ini" foundation/preflight.yml   -e @config/local/foundation.yml -e @"$RUNTIME/host-inputs.yml"   -e foundation_runtime="$RUNTIME"
```

Authenticate host keys out-of-band and enroll the operator's normal SSH known-host
store. Ansible remains strict. After reviewing the isolation requirements above,
the operator may explicitly accept `foundation_operator_accepts_cephadm_ssh_trust_model`.
Separately approve `foundation_allow_ceph_bootstrap` and `foundation_allow_osd_prepare`
in private inputs. No acceptance has been made during development. The sequence is:

```bash
ansible-playbook -i "$RUNTIME/inventory.ini" foundation/ceph.yml   -e @config/local/foundation.yml -e @"$RUNTIME/host-inputs.yml"   -e foundation_runtime="$RUNTIME"
# After Ceph HEALTH_OK: approve foundation_allow_ceph_clients in private inputs.
ansible-playbook -i "$RUNTIME/inventory.ini" foundation/ceph-clients.yml   -e @config/local/foundation.yml -e foundation_runtime="$RUNTIME"
```

Bootstrap installs Podman/LVM/NTP from signed Ubuntu repositories, downloads the
checksummed cephadm archive over verified TLS, bootstraps the first Ceph host,
uses **native fresh FSID generation** (no historical ID argument), enrolls the
native public SSH key, enrolls explicit hosts, places three MON/two MGR daemons,
and writes only explicitly listed OSDs. It waits for HEALTH_OK before recording
the fresh FSID. This is a **fresh-install** sequence: OSD additions are not a
proven idempotent reconciliation/restore workflow. Do not run against an existing
cluster or disks; existing `/etc/ceph/ceph.conf` skips native bootstrap and is not
proof of authorized cluster adoption.

The client play creates named replicated pools `images`, `volumes`, `backups`,
`vms`, initializes RBD and creates pool-scoped clients `glance`, `cinder`,
`cinder-backup`. Nova intentionally shares `client.cinder` per Kolla's native
external-Ceph contract; no admin client is copied. It writes fresh minimal config
with leading tabs removed, and these protected 0600 handoffs:

```text
kolla/config/glance/ceph.conf
kolla/config/glance/ceph.client.glance.keyring
kolla/config/cinder/ceph.conf
kolla/config/cinder/cinder-volume/ceph.client.cinder.keyring
kolla/config/cinder/cinder-backup/ceph.client.cinder.keyring
kolla/config/cinder/cinder-backup/ceph.client.cinder-backup.keyring
kolla/config/nova/ceph.conf
kolla/config/nova/ceph.client.cinder.keyring
```

Supply production PKI material under `$RUNTIME/kolla/certificates/`, all files
0600/directories 0700: `haproxy.pem`, `haproxy-internal.pem` (each certificate chain
plus private key), `backend-cert.pem`, `backend-key.pem`, and `ca/root.crt`.
Backend certificate SANs must cover the backend IPs/names. The trusted CA is
copied into service containers and backend TLS verification remains enabled.
The operator's OS trust must independently recognize this CA.

Only then deliberately execute:

```bash
ALLOW_KOLLA_DEPLOY=reviewed bash "$RUNTIME/kolla-commands.sh"
```

That script uses `umask 077`, native `kolla-genpwd` into
`$RUNTIME/kolla/passwords.yml` only when absent, checks protected Ceph/PKI inputs,
and runs native `bootstrap-servers`, base-only `prechecks`, `deploy`, `post-deploy`,
then the Octavia stages below with the rendered inventory/config directory. Native post-deploy outputs
`admin-openrc.sh` / `clouds.yaml` remain in `$RUNTIME/kolla/`; never print or commit
them. The Terraform producer consumes operator-authenticated cloud access only
after this handoff. No deploy command runs as part of source tests.

## Offline verification / integration

```bash
python -m unittest discover -s foundation/tests -p 'test_*.py' -v
for play in render preflight ceph ceph-clients; do
  ansible-playbook -i "$RUNTIME/inventory.ini" --syntax-check     "foundation/$play.yml" -e @foundation/vars.example.yml     -e @"$RUNTIME/host-inputs.yml"
done
bash -n "$RUNTIME/kolla-commands.sh"
ansible-playbook -i "$RUNTIME/inventory.ini" --syntax-check   "$RUNTIME/venv/share/kolla-ansible/ansible/site.yml"   -e @"$RUNTIME/kolla/globals.yml" -e kolla_action=precheck
```

Tests use stdlib unittest; set `ANSIBLE_PLAYBOOK` to the isolated executable when
it is not on PATH. They execute actual localhost render/inventory parsing,
permission checks, default refusal, provider override contracts and a native
handoff fixture with **inert explicitly labeled test strings**, never real Ceph
keys. Native playbook syntax uses only built-in modules for this directory;
Kolla vendor syntax requires the installed collection above. `tasks/*.yml` are
included task files, **not standalone playbooks**. Syntax requires no live vars
or connections; using the rendered inventory avoids unmatched-group warnings.

Actual offline validation passed against public Kolla 22.2.0/core 2.20.11,
including vendor `site.yml` syntax. This is not host/disk/Ceph/OpenStack convergence
proof. Per-service image digest locking remains a qualification limit, not a
permanent usability gate; production PKI, prepared OS, disk selection and trust enrollment are
explicit external seeds. Bespoke automatic HA/fencing, Watcher controllers and OS
reimaging are outside this baseline. Octavia producers and ordering are below;
live management connectivity and listener forwarding remain unqualified.

## Native Octavia dependency producer (fresh development cloud)

`render.yml` now also produces `amphora-build.sh`, `amphora-register.sh`,
`octavia-certificates.py`, and `octavia-register.yml` in protected runtime.
These are real native entrypoints, not a prerequisite that Octavia already exists.

### Build first, outside the cloud

Use an isolated disposable Ubuntu 24.04 Linux builder with passwordless sudo,
Python venv/pip, curl, git, qemu-utils, kpartx, debootstrap and libguestfs-tools
installed from the signed OS repository. Allocate at least 20 GiB scratch and
adequate memory. No cloud credentials belong on this builder. Copy the rendered
build entrypoint to it using trusted transport, then explicitly run:

```bash
ALLOW_AMPHORA_BUILD=reviewed BUILD_ROOT="$HOME/amphora-build-new" bash amphora-build.sh
```

The entrypoint checksums the actual pinned upstream Octavia source archive and
matching 2026.1 constraints, installs native diskimage-builder 3.40.2, invokes
upstream `diskimage-create/diskimage-create.sh`, pins the Amphora agent Git ref,
uses Ubuntu noble, mandatory access control (`-e`), disk-backed DIB (`-f`), and a
4 GiB QCOW2. It removes generated SSH host keys using only native virt-sysprep's
`ssh-hostkeys` operation and retains qemu validation, info and SHA-512 receipts.
Retain/copy the image and receipts securely before destroying the builder.
Source and constraints hashes in `versions.yml` were measured from public bytes,
not invented. OS mirrors, transitive Git elements/Python packages are not a complete
immutable build BOM. A successful real DIB build is still unqualified here.

### Exact fresh-install order

1. External OS/SSH/network/API-PKI ceremonies; approved Ceph bootstrap, selected
   empty OSDs and pool-scoped client handoff as above. Build/retain Amphora.
2. Native Kolla password template is copied privately before `kolla-genpwd`.
   Native genpwd creates `octavia_amp_ssh_key` (private key stays in runtime).
3. Native bootstrap, base prechecks/deploy with `enable_octavia=no`, post-deploy.
   Identity, Glance, Nova, Neutron, SQL, messaging and toolbox must be healthy.
4. Refresh native `kolla_toolbox` with enabled Octavia cloud configuration.
5. `kolla-ansible deploy -p "$RUNTIME/octavia-register.yml"` imports upstream
   Octavia **tasks_from: register**, not full deploy: creates the dedicated
   `octavia` project/user/admin assignments, catalog/endpoints and load-balancer
   roles before project-owned image registration. The wrapper loads the installed
   22.2.0 group defaults and uses native role/module/filter paths.
6. Operator-authenticated OSC uploads the QCOW2 privately with **owner octavia**,
   tag **amphora**, then reads exact image owner/status/tag/secure hash back.
   Refuses name collisions, invalid/oversized/backed QCOW2 and mismatched hashes.
   Authenticate using protected clouds.yaml/environment; never put passwords in
   shell commands. Fresh cloud authentication must be available at this stage.
7. Explicit isolated Octavia certificate ceremony runs native OpenSSL and writes
   a fresh native `[health_manager] heartbeat_key` override (not upstream `insecure`): separate
   encrypted server/client CAs, client key/CSR and clientAuth certificate. Passwords
   come from protected Kolla YAML into stdin, never secret argv. The generated
   server CA key signs per-Amphora server certificates at service runtime; there
   is deliberately no fabricated static Amphora server identity. Native consumer
   files are `kolla/config/octavia/{server_ca.cert.pem,server_ca.key.pem,
   client_ca.cert.pem,client.cert-and-key.pem}`. Renewal material stays in
   `$RUNTIME/octavia-ca` (0700). Refuses overwrite/reissuance; secure backup and
   eventual renewal are operator ceremonies. No keys were generated in development.
8. Full native prechecks and **full fresh-install deploy**, not a partial
   `--tags octavia` approximation. This applies shared toolbox/Horizon/proxy/SQL
   dependencies, then upstream Octavia `register -> prepare -> config-host ->
   config -> check-containers -> bootstrap -> handlers`. Native `prepare.yml`
   creates flavor, Nova SSH keypair, SG/rules, private management network/subnet;
   `config-host.yml -> hm-interface.yml` creates controller health-manager ports,
   binds them to OVS and starts `o-hm0`/dhclient. Final post-deploy is the handoff.
9. Only after live API/management-path qualification and a disposable
   ACTIVE/ONLINE load balancer with real listener-to-member forwarding should
   downstream lab-02 load-balancer exercises be accepted.

The generated driver implements this sequence and sources the freshly generated
protected native `admin-openrc.sh` after base post-deploy with tracing disabled.
After approving each ceremony (credentials remain runtime/process-only):

```bash
export AMPHORA_IMAGE=/absolute/retained/amphora.qcow2
export ALLOW_AMPHORA_REGISTER=reviewed
export ALLOW_PROVIDER_ASSETS=reviewed
export ALLOW_OCTAVIA_CERTIFICATES=reviewed
ALLOW_KOLLA_DEPLOY=reviewed bash "$RUNTIME/kolla-commands.sh"
```

This is intentionally a fresh-install driver, not a resumable existing-cloud
updater. Certificate/image stages refuse overwrite; after interruption inspect
retained stage receipts and run the individually documented native stages, never
blindly rerun or delete existing resources.

Tenant-management mode is native OVS development/testing mode, not production
network availability. Review `foundation_octavia_management_cidr` against ALL
routes/subnets; install `/sbin/dhclient` on health-manager controllers from signed
Ubuntu packages before deployment. Kolla's native SG task does not pass remote
CIDR restrictions: management SG permits ICMP/TCP22/TCP9443, health-manager UDP5555;
protect the dedicated private network, do not claim CIDR-narrowed native rules.
SINGLE Amphora topology is not HA. No changes to the provider VLAN/physical path.

**Verified native sources:** Kolla 22.2.0 commit
`a3badc9325e53d875b30f3b89947e7e2e2863781`, `ansible/group_vars/all/octavia.yml`,
`roles/octavia/{defaults/main.yml,tasks/register.yml,tasks/prepare.yml,
 tasks/deploy.yml,tasks/config-host.yml,tasks/hm-interface.yml}`, certificate
role output contract and `kolla_ansible/cmd/genpwd.py`. Native CLI `deploy --help`
supports `-p/--playbook`, configdir/passwords/tags. Upstream certificate role
puts passphrases in argv, so this kit uses native OpenSSL with stdin rather than
claiming `no_log` fixes argv. Upstream tenant health-manager port-binding task
also passes an Octavia password in command argv; restrict privileged host/process
access and retain that upstream exposure as a real native boundary. Do not run
Kolla with debug/diff or publish native logs/password bundles. No Ansible SSH/TLS
verification bypass or vendor patch is supplied.

## External provider asset handoff

Kolla creates br-ex/services, **not** the Neutron external `public` asset looked
up by downstream Terraform. `provider-assets.sh` is rendered from the same private
reviewed `config/local/foundation.yml` seed and runs after base post-deploy, before
Octavia registration and all tenant Terraform. Its configurable `foundation_provider_*`
inputs cover name, flat/vlan type, VLAN ID, physnet, owner project, subnet name,
CIDR, gateway and allocation-pool endpoints. Example `198.51.100.0/24` is fictional:
replace it and all host seeds before setting `foundation_inputs_reviewed: true`
and re-rendering. ML2 VLAN range and provider VLAN inputs must agree.

The native OSC producer requires `ALLOW_PROVIDER_ASSETS=reviewed`. It validates
IPv4 pool/gateway membership and separation, reads existing name matches, refuses
duplicates, checks owner/external/shared/type/physnet/VLAN before reuse, and checks
subnet owner/network/name/CIDR/gateway/DHCP/pool. It creates only missing targets,
never modifies mismatched existing assets, and reads exact created IDs back.
Private receipts are `$RUNTIME/provider-assets/{network,subnet}.json`.
For isolated stage execution after native authentication:

```bash
ALLOW_PROVIDER_ASSETS=reviewed bash "$RUNTIME/provider-assets.sh"
```

Install the pinned OSC from `requirements.txt`; no provider command is executed
by source tests. Provider validation is exercised using explicitly inert native
JSON fixtures, including rejection of a mismatched VLAN. Native CLI/schema checks
are not evidence that switch trunk, external routing or floating-IP reachability
works. Those require later operator acceptance before tenant Terraform.
