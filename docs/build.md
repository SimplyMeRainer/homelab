# Build order

Build from the bottom up. A successful parser or plan is not permission to skip a dependency or point a command at an existing production environment.

## 0. Prepare the seed infrastructure

You need five prepared Ubuntu 24.04 Linux hosts, a persistent Linux Docker management host or compatible NAS, and a separate supported FreeIPA-server guest. Install operating systems through your normal hardware/vendor workflow. Keep console access and recovery media available.

Before starting, establish:

- A reviewed management/provider/tenant/pod/service address plan, working routing and a single owner for each VLAN tag.
- Forward/reverse DNS, working package-repository resolution and time synchronization.
- Trusted administrator SSH, authenticated host keys and explicitly selected empty OSD disks.
- Adequate CPU/RAM/storage and the switch connectivity required by the configured interfaces.
- A private operator workstation, trusted CA enrollment and an encrypted backup location for generated state and secrets.

The documentation ranges and `.example` names are not usable deployment inputs. Individual examples illustrate a component; they are not a global IPAM allocation. Replace them together and check for overlap. Do not reuse an existing cluster's state, disks or identity to make a fresh build appear complete.

## 1. Render and build the cloud foundation

Follow [foundation/README.md](../foundation/README.md). Copy its variable example into ignored `config/local/`, review host roles/NICs/disk IDs and render the native inventory and Kolla configuration into `runtime/foundation/`.

Run its read-only preflight before selecting any execution opt-in. The foundation guide owns Ceph bootstrap, client-key handoff, provider-network setup, Octavia dependencies and the Kolla command order. Inspect the documented upstream cephadm SSH trust boundary rather than assuming Ansible's host-key policy also controls the manager's SSH client.

Do not proceed to tenant Terraform until the intended OpenStack services, provider network, external-Ceph clients and Octavia dependencies exist. Keep Kolla-generated cloud credentials private; select the intended cloud profile explicitly before running the OpenStack CLI or Terraform.

## 2. Install identity and management services

Follow [services/README.md](../services/README.md) from its stated entry directory. The identity VM is separate from the workload clusters. It needs its own prepared OS, DNS, time and trusted SSH before the official FreeIPA role runs.

Create fresh PKI and independent secret files, transfer only the required leaves/public trust, and set ownership for the actual container UIDs. Keep CA private keys offline. Install the management stack with native Compose only after validating its normalized configuration and reviewing every host binding.

Vault initialization/unseal, directory membership, application enrollment and first-owner setup are security ceremonies, not CI jobs. Keycloak installation alone does not make every application directory-authenticated. The service guide states the actual integration boundaries and acceptance checks.

MinIO uses a checksum-pinned upstream source build because official anonymous image pulls were denied during development. Build it using the supplied Dockerfile; retain and scan the resulting artifact before deployment. Do not invent a registry digest or replace it with an unrelated image.

## 3. Produce cloud assets and VM cohorts

Follow [terraform/README.md](../terraform/README.md):

1. Authenticate and checksum the Ubuntu cloud image.
2. Apply `terraform/cloud-assets` in the intended cloud/project; it produces image/flavor names consumed by the other roots.
3. Review separate plans for `terraform/lab-01`, `terraform/lab-02` and `terraform/rancher-management`.
4. Apply each approved saved plan using its own protected backend/state.
5. Export each root's native `ansible_inventory` and `nodes` outputs into its private runtime directory.

The source looks up or produces named assets rather than requiring repeated manual UUID discovery. Public keys are inputs; no Terraform resource creates an SSH private key. Quota and a successful plan do not prove hypervisor capacity or placement.

Administration of private API VIPs requires a real route/VPN into the tenant networks. A working floating-IP SSH connection does not establish that route.

## 4. Build both Kubernetes labs

### lab-01: repeatable setup

Use [ansible/README.md](../ansible/README.md). Export its Terraform inventory, review a private operator file and run `baseline.yml`, then `site.yml`. The full inventory is required. The site play owns the serial three-control-plane bootstrap, kube-vip transition, Cilium, two worker joins and private kubeconfig output.

The automation refuses an unowned/mismatched cluster and ambiguous partial initialization. Read its recovery boundary; do not remove ownership markers or reset etcd to make a rerun pass.

### lab-02: manual Kubernetes build

Run the Ansible baseline with the separate lab-02 inventory, then follow [kubernetes/lab-02/README.md](../kubernetes/lab-02/README.md). Terraform creates three control planes, three workers and distinct Octavia API/ingress load balancers. Kubernetes installation remains manual. Do not install kube-vip over the Octavia API design.

## 5. Connect storage, backup and management

Use the explicitly selected cluster kubeconfig/context for every command:

- [Cinder CSI and the retained storage class](../kubernetes/storage/README.md).
- [Velero/Kopia with scoped MinIO credentials and trusted TLS](../kubernetes/backup/README.md).
- [Separate management-cluster and Rancher installation](../kubernetes/rancher/README.md).

Install integrations on each intended cluster; installing one on lab-01 does not configure lab-02. A retained Cinder volume is not a backup. Keep the Velero bucket dedicated to its supported layout.

## 6. Validate the deployed result

Publication-time CI does not perform these checks. Before treating a deployment as usable, verify cloud service health, actual host placement, intended routes/MTU, load-balancer members, three-member etcd/API health, Cilium traffic and Cinder volume attachment.

Then exercise fresh allowed/denied identity logins, local recovery access, a small backup/restore with a data-integrity check, and safe restart/persistence tests. Plan outage/HA drills separately. Record the actual source revision, edited inputs and results privately; do not publish cloud responses or credentials as evidence.

## Where to edit

| Change | Source input |
|---|---|
| Physical topology, interfaces, disks and cloud settings | `foundation/vars.example.yml` copied to private configuration |
| Native platform dependency versions | `foundation/versions.yml`, foundation requirements |
| Image, flavors and cloud asset names | `terraform/cloud-assets/terraform.tfvars.example` and variables |
| Per-cluster networking, access and image/flavor selection | Each Terraform root's `terraform.tfvars.example` |
| Kubernetes packages and bootstrap behavior | `ansible/vars/releases.yml`, private operator file |
| Manual cluster setup and chart versions | `kubernetes/versions.yaml`, `kubernetes/charts.lock.json` |
| Service names, bindings, secrets/TLS paths | `services/management.env.example`, copied privately |
| Service images and identity/client configuration | `services/images.lock.json`, Compose and component configuration |

Keep real inputs in ignored files. Update matching consumers and tests when changing a shared version or interface. Never edit generated runtime output as a substitute for changing its source.
