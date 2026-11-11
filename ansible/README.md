# Native Ubuntu / kubeadm bootstrap

Two explicit entrypoints; no Python provisioning controller, SSH wrapper, cloud API call, or custom collection:

* `baseline.yml`: Ubuntu **24.04**, distro **containerd 1.7 / CRI v1**, systemd cgroups, forwarding/modules, safe swap disable, official Kubernetes apt signing key/repository, exact kubeadm/kubelet/kubectl **1.35.10-1.1**, package holds. Works for fresh **lab-01 and lab-02**, and matching kit-owned same-version resume. A separate read-only all-target admission play runs before the first fstab/runtime/package mutation. It does not create a cluster.
* `site.yml`: **lab-01 only**, exactly **3 control planes / 2 workers**. Read-only ownership checks precede mutations across all guests. Initializes the first inventory control plane, bootstraps an ARP kube-vip private API VIP, installs Cilium, serially joins the other control planes, joins workers, verifies readiness, and writes a standalone private kubeconfig. It never runs baseline implicitly.

This is source plus offline validation, **not a demonstrated live install or clean-room rebuild**. No infrastructure access is required by the tests. The automation is fresh-install / same-version resume, not an upgrade, cluster adoption, disaster-recovery, or certificate-rotation tool.

## Required private inputs and prepared infrastructure

1. Prepared Ubuntu 24.04 guests, Python 3, sudo/root privilege, working clock/DNS, adequate disks/resources, and outbound HTTPS to Ubuntu, pkgs.k8s.io and the public image registries. OS installation is an explicit prerequisite.
2. An operator-controlled SSH identity (not included here), the image's SSH user, and **independently authenticated host keys** in the controller's normal `known_hosts`. Enroll fingerprints using a trusted image/console channel; an unauthenticated `ssh-keyscan` alone is not trust. Host-key checking remains enabled, agent forwarding disabled. Do not pass keys/passwords as extra-var literals or commit them.
3. Separately reviewed Terraform project/network inputs and state for the intended lab. Terraform supplies floating SSH `ansible_host` and private `node_ip`; **never advertise a floating SSH address to kubeadm**. No project UUID, source image UUID, or real address is embedded here.
4. A reserved, unallocated private `api_vip` on the control planes' common L2 subnet, correct private `kube_vip_interface`, API endpoint DNS resolution on guests/controller, and endpoint reachability from the administration network. OpenStack ports must allow the VIP using the foundation's allowed-address-pair/port-security design. ARP VIP is not an Octavia endpoint. Check tenant MTU and firewall/security groups for Kubernetes API, etcd/control-plane traffic, kubelet, and Cilium VXLAN/health traffic; do not expose etcd to public networks.
5. Nonoverlapping pod/service/infrastructure/VPN networks. The `10.244.0.0/16` and `10.96.0.0/16` examples are illustrative fresh allocations, not copied deployed networks. Every `192.0.2.0/24` / `203.0.113.0/24` and `*.example` value is fictional and must be replaced privately.
6. On the controller: native Terraform, Helm 3 or 4, and Ansible core. The reproducible baseline is `requirements.txt` (core 2.20.11, Python 3.12+). Only `ansible.builtin` is used; no `ansible-galaxy` collection install is needed. Helm renders the verified upstream chart locally; it is not installed on guests. Both core 2.20 and 2.21 have offline coverage.

Inventory contract: groups `control_plane` and `worker`; `all.vars` contains `cluster_name`, `kube_context`, `api_endpoint` (host:6443, no scheme), `api_vip`, `pod_cidr`, `service_cidr`; every host has `ansible_host` and `node_ip`. Inventory hostnames become Kubernetes node names and must be DNS labels. The first control-plane inventory entry is the bootstrap node. Keep that order and the entire inventory stable for resume. `inventory.example.yml` documents the schema, not a runnable real environment.

## Exact native invocation (from repository root)

The following are operator deployment commands; they were **not run against guests during publication**. `LAB_TF` must identify your already applied **lab-01 Terraform root/state**, not foundation state or lab-02. Terraform output reads local/backend state with your separately supplied authorized project credentials; Ansible does not read OpenRC or cloud credentials.

```sh
umask 077
install -d -m 700 runtime/ansible/lab-01 config/local
python3 -m venv runtime/ansible-venv
runtime/ansible-venv/bin/python -m pip install -r ansible/requirements.txt
export PATH="$PWD/runtime/ansible-venv/bin:$PATH"
export ANSIBLE_CONFIG="$PWD/ansible/ansible.cfg"

# Set to the absolute directory of your applied lab-01 Terraform configuration.
export LAB_TF=/absolute/path/to/applied/lab-01
terraform -chdir="$LAB_TF" output -raw ansible_inventory \
  > runtime/ansible/lab-01/inventory.yml
chmod 600 runtime/ansible/lab-01/inventory.yml
cp ansible/operator.example.yml config/local/lab-01-ansible.yml
chmod 600 config/local/lab-01-ansible.yml
# Edit the private file: actual SSH user, identity PATH, private NIC;
# set lab_inputs_confirmed: true only after reviewing the entire inventory.
# Do not copy key material into that YAML; a private key PATH is sufficient.

ansible-inventory -i runtime/ansible/lab-01/inventory.yml --graph
ansible-playbook -i runtime/ansible/lab-01/inventory.yml ansible/baseline.yml \
  -e @config/local/lab-01-ansible.yml --ask-become-pass
ansible-playbook -i runtime/ansible/lab-01/inventory.yml ansible/site.yml \
  -e @config/local/lab-01-ansible.yml --ask-become-pass

kubectl --kubeconfig runtime/ansible/lab-01/admin.kubeconfig \
  --context lab-01-admin@lab-01 --request-timeout=10s get nodes -o wide
```

Omit `--ask-become-pass` only for a deliberately configured passwordless-sudo operator. No insecure TLS flag is needed or supported. The output directory is mode **0700**, inventory/kubeconfig **0600**; do not upload it to CI. `bootstrap_output_dir` may select another absolute private directory. Never point it at `~/.kube/config`: output contains only one cluster/context and does not merge or change your default kubeconfig.

### lab-02 is baseline + manual cluster construction

Read native `ansible_inventory` from the separately applied lab-02 Terraform root into `runtime/ansible/lab-02/inventory.yml`, and use a separate private operator file. Run **only `baseline.yml`** with that inventory. Continue with the lab-02 manual Kubernetes / Octavia procedure in the `kubernetes/` source and documentation. Do not substitute the lab-01 kube-vip VIP for the lab-02 load-balancer endpoint. `site.yml` rejects `cluster_name: lab-02` on localhost **before any guest connection or mutation**.

## Bootstrap, secrets, reruns and partial resume

Both entrypoints reuse `roles/cluster/tasks/preflight.yml` and `state-admission.yml` across **every** target in a separate fatal-on-error play before any guest mutation. This also protects the documented **baseline -> site** route: unmarked existing kubeadm/etcd state, changed immutable ownership, the first control plane's partial-init boundary, other nodes' partial-join state, and **all existing kubelets' actual CA/endpoint** are admitted before baseline's first fstab change or site's first ownership/configuration/VIP/Cilium write. Existing kubelets require the first control plane's readable `admin.conf` as the authoritative CA; a completely fresh lab with no kubelet state needs no `admin.conf`. These are file/state checks, not live API/readiness proof. The serial init/join stages reuse the same state checks immediately before their writes and retain the later authenticated readiness gates and secret cleanup. This is not a lock against concurrent/manual state changes; parallel runs remain unsupported.

Fresh lab-02 baseline remains supported with the complete Terraform inventory and operator inputs, but manually constructed **unmarked** lab-02 clusters are not adopted by later baseline runs. Plan any subsequent OS maintenance separately rather than bypass admission.

* For Kubernetes >=1.29, `admin.conf` lacks the required RBAC during bootstrap. Native kubeadm preflight/certificate/kubeconfig phases run first, then kube-vip gets a **node-local API** copy of `super-admin.conf`. This avoids a VIP/leader-election dependency cycle. After successful init and authenticated `/readyz`, kube-vip switches to a node-local copy of **regular `admin.conf`**. The credential-source annotation changes the static pod hash, forcing a restart so a file bind mount cannot retain bootstrap credentials. `super-admin.conf` is never exported to the controller. Keep its on-node original root-private for deliberate break-glass handling.
* Kubeadm init/join output is `no_log`; runtime discovery tokens have a ten-minute TTL and are immediately revoked. CA-pinned discovery never uses `unsafeSkipCAVerification`. Each serialized control-plane join generates a fresh certificate encryption key and uses native encrypted `upload-certs`; keys/tokens stay in memory and a temporary root-private JoinConfiguration, not Git or facts cache. The join file is removed in `always`, and the uploaded certificate Secret is deleted after each control-plane enrollment. Do not enable callback/debug logging or `--diff` around secrets. If cleanup loses API access, token expiry and kubeadm's two-hour certificate-secret expiry are backstops, not proof of immediate revocation.
* Cilium keeps kube-proxy, uses Kubernetes pod-CIDR IPAM, and is rendered by controller Helm from a checksum-pinned chart whose image digests remain enabled. Optional Hubble is **disabled**, not made plaintext: the default Helm TLS certificate generation would otherwise rotate secrets on every offline render. This baseline is not a Helm-managed release; reconcile with the same native server-side apply owner. Do not install a second CNI over it.
* Kubernetes 1.35 locks `ControlPlaneKubeletLocalMode` on: existing control-plane kubelets are checked against their private local API endpoint, workers against the shared endpoint, and both against the authoritative cluster CA. This is not a TLS verification bypass.
* On a normal rerun, completed init/join are skipped, identity/CA/endpoint are verified, Cilium is reconciled, and readiness/output are refreshed. No new token or certificate upload is needed for already joined nodes. Marker identity freezes version, topology/order, private address, VIP, endpoint and CIDRs. Changing those inputs is intentionally refused rather than treated as an upgrade.
* `/etc/kubernetes/lab-kit-identity.json` records ownership. Unmarked existing kubeadm/etcd state is refused. The first node's `lab-kit-init-complete` is written **only after successful native init**. Failure before certificates/kubeconfigs exist is safely retried. Interruption after that state is created but before successful completion is an **ambiguous partial init** and stops with a recovery message—no automatic reset/deletion/re-init. Inspect kubeadm phase output via root-only local diagnostics and decide an audited manual phase recovery or restore/fresh-guest replacement. If manually completing an interrupted init, verify the pinned config, authenticated `/readyz` and live kubeadm-config identity before recording the completion boundary; never manufacture the marker to suppress a failure. A normal rerun then finishes the admin credential switch/CNI/joins.
* Completed joins can resume through readiness/CNI/output failures without issuing new secrets. A failed partial join without kubelet.conf is refused if PKI/other state exists. A kubelet.conf from a partial join must pass authoritative CA/endpoint and Ready checks; a partial control-plane join must also provide a working local admin API. Diagnose/recover manually rather than remove the marker, reset a member, or continue past failure.
* Run the full inventory. `--limit`, `--start-at-task`, tags/skipping safety tasks, parallel site runs, restoring an old marker, and `--check` as a deployment simulation are unsupported. `--limit` is guarded on guests as well as localhost; `site.yml --check` explicitly refuses. Never repair a mismatched cluster by deleting its identity file. No automatic reset or etcd member removal exists.

## Verified public pins

`vars/releases.yml` is the review point. Values were checked against public upstream, not guessed from a private package string:

* [Official Kubernetes v1.35 Packages](https://pkgs.k8s.io/core:/stable:/v1.35/deb/Packages) contains `1.35.10-1.1` for kubeadm/kubelet/kubectl; the ASCII [Release.key](https://pkgs.k8s.io/core:/stable:/v1.35/deb/Release.key) is checksum-pinned. Key rotation should fail closed and requires a reviewed pin update.
* [Kubeadm v1.35.10 constants](https://github.com/kubernetes/kubernetes/blob/v1.35.10/cmd/kubeadm/app/constants/constants.go) selects pause `3.10.1`; containerd uses its verified registry manifest-list digest. Containerd itself is Ubuntu's security-maintained 1.7 package, explicitly checked at runtime; this is not a digest-pinned OS snapshot or a generic containerd 2 config.
* [kube-vip v1.3.1](https://github.com/kube-vip/kube-vip/releases/tag/v1.3.1): GHCR OCI index digest `sha256:1962f9daf226503f7e6b107f595cb28b7917fd2d0113957075e19a3e5a6c1e33`. [Official static-pod guide](https://kube-vip.io/docs/installation/static/) documents the >=1.29 super-admin bootstrap distinction. The published pin is multi-architecture, not an invented platform manifest.
* [Cilium chart 1.19.10](https://helm.cilium.io/cilium-1.19.10.tgz): SHA256 `b7252afca3413a33e2b987c954e52441e96979e411e1495ecc6aefe8cd258863`, matched against the [official index](https://helm.cilium.io/index.yaml). [Release-specific compatibility](https://github.com/cilium/cilium/blob/v1.19.10/Documentation/network/kubernetes/compatibility.rst) includes Kubernetes 1.35. The chart's Cilium/operator/Envoy images render with upstream immutable digests.

## Offline validation (no credentials, guests, or cluster)

From the repository root with the controller venv active:

```sh
export ANSIBLE_CONFIG="$PWD/ansible/ansible.cfg"
ansible-playbook -i ansible/inventory.example.yml ansible/baseline.yml --syntax-check
ansible-playbook -i ansible/inventory.example.yml ansible/site.yml --syntax-check
python -m unittest discover -s ansible/tests -p 'test_*.py' -v
```

Tests use stdlib unittest plus PyYAML (already a core Ansible dependency), and real local `ansible-playbook` subprocesses. `ANSIBLE_PLAYBOOK` may select an absolute executable. They exercise tab-separated swap persistence on a disposable fstab twice (second run unchanged), production template rendering and 0600 private single-context output, matching/mismatched ownership assertions, the real native readiness command with a controlled inert executable, and lab-02 rejection without SSH. Actual `baseline.yml` and `site.yml` ordering regressions use a **test-only controlled linear strategy/action observer**: native coordination/includes/assertions run unchanged, setup/stat/slurp return bounded inert observations, and every other I/O action fails closed at a logged first-mutation sentinel. Unsafe later nodes must produce zero sentinel events; fresh lab-01/lab-02 baselines, fresh site without admin.conf, and matching resume must reach that sentinel only after all-target admission. These tests stop **before** the first mutation; they do not simulate successful provisioning. The custom strategy is confined to tests and relies on the pinned Ansible core API (third-party strategy support is deprecated upstream). No fixture installs packages, runs kubeadm, or calls an API. All temporary writes are controller-local. Native syntax checks also succeed with `-i localhost,` (unmatched guest-group warnings are expected).

Public-upstream verification additionally downloaded the actual Cilium chart, rendered it with native Helm, checked image digests and compared two renders with optional Hubble disabled. These are offline render checks, not a real install, Kubernetes schema admission test, CRI/cgroup guest test, HA failover test, or proof of live idempotent convergence. First authorized deployment still needs Ubuntu package/CRI checks, end-to-end connectivity, reboot/swap validation, actual 3-member etcd/API health, Cilium traffic tests and VIP failover observation.
