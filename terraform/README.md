# Native OpenStack producers and independently stated clusters

Terraform **1.16.5**, OpenStack provider **3.4.0**, Ubuntu **24.04 amd64**.
These files create infrastructure only. There is no cloud-init Kubernetes installation,
remote/local execution, generated private key or assistant provisioning wrapper.

| Root (separate state) | Owns |
|---|---|
| `cloud-assets` | SHA256-checked local Glance image, three private Nova flavors and current-project grants, Amphora ACTIVE_STANDBY Octavia profile/flavor |
| `lab-01` | 3 control planes + 2 workers, reserved kube-vip address + CP allowed-address-pairs |
| `lab-02` | 3 control planes + 3 workers, independent ACTIVE_STANDBY API and ingress Octavia LBs, TCP health monitors |
| `rancher-management` | 1 dedicated management VM; single-node K3s + Rancher path in `../kubernetes/rancher/README.md` |

## Prerequisites and boundaries

Complete the foundation first: Neutron L3/DHCP/metadata, external provider network,
Glance, Nova, Cinder backed by Ceph, Octavia Amphora image/network/certificates and
working ACTIVE_STANDBY provider are required. Terraform creates the Octavia flavor,
not Octavia's underlying service or Amphora appliance image. The provisioning
identity needs permissions to create private flavors/flavor grants and Octavia flavor
profiles; use the intended lab project with those administrator permissions. All four
roots use that **same project and Nova user** (keypairs are user-scoped). Authenticate
externally via `OS_CLOUD`, `OS_CLIENT_CONFIG_FILE`, trusted cloud CA and a protected
clouds.yaml/application credential. No credentials in HCL/tfvars. Never disable TLS.
Flavors and image names must be unique; all IDs flow from resources/data sources.

Check project quotas, floating-IP pool, Octavia quota (two active/standby LBs require
four Amphorae), CPU/RAM/disk and host capacity before applying. Each workload lab
creates its own hard `anti-affinity` Nova server group and sends **only its three
control-plane VMs** to that group with `scheduler_hints`. At least three eligible
compute hosts with capacity are required; Nova must reject an unschedulable hard
policy, not silently fall back to colocation. Workers and the separate Rancher
management VM have no control-plane placement hint. No deployment was
performed by this kit's offline tests; no clean-room rebuild claim is made.

All example IPs are documentation-only ranges. **Replace** tenant CIDRs, administrator
CIDRs, DNS servers and cloud network name before deployment; choose /24 tenant
subnets, distinct from the external network, each other, management, pods and services.
The module reserves .10 for kube-vip, .11-.13 for CPs, .21-.23 for workers and .100-.200
for DHCP/Octavia. These seed examples are not a global allocation plan.
Public endpoint/listener access is restricted to valid IPv4 `admin_cidrs`,
including ingress: expand only to explicitly intended client CIDRs, never /0.
Egress is allowed for package downloads. Internal node traffic is restricted to the
cluster security group; Octavia member ports permit the dedicated tenant subnet.
Floating IPs expose SSH for Ansible under the same administrator allowlist.

## Exact native build sequence

Commands run from the repository root, on a prepared operator workstation. Use umask
077 for every step. The following are **operator deployment instructions**, not CI commands.
The Ubuntu image may be downloaded on a Linux workstation with the official
`ubuntu-cloudimage-keyring` installed/trusted through Ubuntu's package distribution.
On macOS obtain the official signing key through Ubuntu's documented authenticated
process; do not fetch a key blindly from a keyserver and call that verification.

```sh
umask 077
mkdir -p runtime/images runtime/terraform/{cloud-assets,lab-01,lab-02,rancher-management}
chmod 700 runtime runtime/images runtime/terraform runtime/terraform/*
curl --fail --location https://cloud-images.ubuntu.com/noble/current/SHA256SUMS -o runtime/images/SHA256SUMS
curl --fail --location https://cloud-images.ubuntu.com/noble/current/SHA256SUMS.gpg -o runtime/images/SHA256SUMS.gpg
curl --fail --location https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img -o runtime/images/noble-server-cloudimg-amd64.img
gpgv --keyring /usr/share/keyrings/ubuntu-cloudimage-keyring.gpg runtime/images/SHA256SUMS.gpg runtime/images/SHA256SUMS
(cd runtime/images && grep ' noble-server-cloudimg-amd64.img$' SHA256SUMS | sha256sum --check -)
cp terraform/cloud-assets/terraform.tfvars.example runtime/terraform/cloud-assets/inputs.tfvars
```

Edit inputs: local image path is resolved from `terraform/cloud-assets/`, and
`image_sha256` is the exact authenticated checksum above. Retain the dated upstream
image URL and signed checksum files in private deployment records. A changing `current`
image fails closed if its bytes differ. Terraform independently runs `filesha256`
before allowing the upload; the included five-byte test fixture is **not an image**.
The actual file SHA256 is a native `terraform_data.triggers_replace` input bound to
Glance through `replace_triggered_by`. Changed bytes at the **same path**, even with
an updated correct expected checksum, therefore require image replacement rather
than relabeling a reused image. The image's `prevent_destroy` guard blocks that
replacement until the deliberate ceremony below. The output checksum comes from
the same actual-content lifecycle input, not an unbound operator claim.

Use a separate working directory and protected state for each root. `path` below is
relative to the root directory selected by `-chdir`; do not share one backend file.

```sh
terraform -chdir=terraform/cloud-assets init -backend-config="path=$PWD/runtime/terraform/cloud-assets/terraform.tfstate"
terraform -chdir=terraform/cloud-assets plan -state=../../runtime/terraform/cloud-assets/terraform.tfstate -var-file=../../runtime/terraform/cloud-assets/inputs.tfvars -out=../../runtime/terraform/cloud-assets/plan
terraform -chdir=terraform/cloud-assets show -no-color ../../runtime/terraform/cloud-assets/plan
# STOP: review the saved plan under the destructive-action boundary below.
terraform -chdir=terraform/cloud-assets apply ../../runtime/terraform/cloud-assets/plan
terraform -chdir=terraform/cloud-assets output -state=../../runtime/terraform/cloud-assets/terraform.tfstate -json
```

For each of `lab-01`, `lab-02`, `rancher-management`, copy its tfvars example to
`runtime/terraform/ROOT/inputs.tfvars`. Edit the placeholder public key with the
contents of an **existing .pub** file, cloud network name, CIDRs and resolver addresses.
Use the image/flavor **names** produced above (defaults already match), including
`kit-management` for the management VM. There is no manual UUID lookup. Lab-02
`octavia_flavor_name` matches the produced `active-standby` name.

```sh
ROOT=lab-01  # repeat independently for lab-02 and rancher-management
terraform -chdir=terraform/$ROOT init -backend-config="path=$PWD/runtime/terraform/$ROOT/terraform.tfstate"
terraform -chdir=terraform/$ROOT plan -state=../../runtime/terraform/$ROOT/terraform.tfstate -var-file=../../runtime/terraform/$ROOT/inputs.tfvars -out=../../runtime/terraform/$ROOT/plan
terraform -chdir=terraform/$ROOT show -no-color ../../runtime/terraform/$ROOT/plan
# STOP: review the saved plan under the destructive-action boundary below.
terraform -chdir=terraform/$ROOT apply ../../runtime/terraform/$ROOT/plan
terraform -chdir=terraform/$ROOT output -state=../../runtime/terraform/$ROOT/terraform.tfstate -raw ansible_inventory > runtime/terraform/$ROOT/inventory.yaml
terraform -chdir=terraform/$ROOT output -state=../../runtime/terraform/$ROOT/terraform.tfstate -json nodes > runtime/terraform/$ROOT/nodes.json
chmod 600 runtime/terraform/$ROOT/*
```

Local backend paths use explicit `-state` for plan/output; an apply of a saved plan uses
its recorded backend/state. For remote state replace these instructions with one
independently configured encrypted/locked backend per root; never mix approaches.
Protect state, saved plans and backups as secrets even though no password is an input.

## Deliberate replacement and destruction boundary

All Nova VMs, the Glance image and the three flavors have literal native
`lifecycle { prevent_destroy = true }` protection. An existing-resource destroy or
replacement plan must fail while the relevant guard remains enabled. A saved plan
alone is **not** approval. Do not use `-target`, state removal, resource-block removal
or a different state to evade a failure. Terraform cannot protect a resource after
its entire declaration has been removed; retain the configuration and state.

For an intentional change, the operator must:

1. Stop concurrent operations, back up protected state and workload data, verify a
   restore path, and identify affected resource addresses and consumers. Image and
   flavor changes need review across **all three consumer states**, not just assets.
   Prefer a separately named/versioned asset and deliberate consumer migration.
2. Record the exact replacement/deletion addresses, expected downtime, recovery
   plan and explicit operator acceptance in private change records. For a one-node
   replacement, isolate that exact VM instance in reviewed HCL before changing its
   guard; the shared `for_each` guard otherwise covers every VM in that module.
3. Only after approval, temporarily change the **relevant literal** `prevent_destroy`
   to `false` in a reviewed local change. Do not remove the resource declaration or
   the image's content trigger. This is not a normal tfvars switch.
4. Generate a **fresh** saved plan with the documented native command. Run
   `terraform -chdir=terraform/ROOT show -no-color /absolute/path/to/plan` and inspect
   every `destroy`, `-/+` and `+/-` action. Explicitly accept only the documented
   addresses; reject unrelated actions and regenerate after any input/source change.
   Never apply an earlier plan created before this review.
5. Apply only that reviewed saved plan, restore `prevent_destroy = true` immediately,
   then make and inspect a fresh normal plan. Verify resource identity, consumers
   and recovery acceptance before closing the change. Teardown uses the same
   ceremony, consumer states first and cloud-assets last.

This boundary is native Terraform, not an automatic replacement/provisioning wrapper.
It does not prove backups, physical placement, schedulability or cloud health.

## Handoffs and endpoint semantics

`nodes` maps hostnames to `role`, Nova `id`, tenant `node_ip`, floating `ansible_host`.
`ansible_inventory` is YAML string: `all.children.control_plane.hosts` and
`all.children.worker.hosts`; each host has `ansible_host` and `node_ip`.
`all.vars` has `cluster_name`, `kube_context` (`lab-01-admin@lab-01` for lab-01),
`api_endpoint` (`address:6443`), `api_vip`, `pod_cidr`, `service_cidr`.

The canonical API is **private**: kube-vip tenant VIP for lab-01, Octavia private
API VIP for lab-02. The operator must have a real routed/VPN path into tenant
networks; SSH floating IP reachability alone does not give kubectl API reachability.
Lab-02 also outputs `api_floating_ip` (add to kubeadm cert SANs before bootstrap)
and `ingress_floating_ip` (DNS for application ingresses). TLS terminates in Traefik,
not Octavia. API and ingress do not share a VIP or pool. A TCP check is not `/readyz`.
Neutron permitted-address-pairs and layer-2 ARP delivery must be verified before
lab-01 kube-vip bootstrap; never bind a floating IP inside a guest.

Use `ansible/README.md` to baseline both labs and automate **lab-01 only**;
`kubernetes/lab-02/README.md` owns manual lab-02 installation. Terraform outputs are
consumable directly; no script translates inventory. Management instructions are
separate and do not count its VM as either workload lab.

## Offline native checks

```sh
terraform fmt -check -recursive terraform
for ROOT in cloud-assets lab-01 lab-02 rancher-management; do
  terraform -chdir=terraform/$ROOT init -backend=false
  terraform -chdir=terraform/$ROOT validate
  terraform -chdir=terraform/$ROOT test
 done
```

All `.tftest.hcl` files use native `mock_provider "openstack"`; plan assertions
exercise counts and wiring, and a mocked apply checks decoded inventory, without
any cloud request. They do **not** prove image
bootability, quotas, packet paths, Octavia failover, CSI attachment or guest convergence.
Destroy consumers in reverse order only after backup/recovery review. Do not destroy
cloud-assets while either lab/management VM still depends on its image or flavors.
