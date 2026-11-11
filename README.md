# My homelab

I use this lab to practice running a small private cloud: building VMs, connecting storage, running two Kubernetes labs, and recovering an application after a rebuild.

It runs on five reused Linux machines and a NAS. I care more about understanding failures and making changes repeatable than collecting tools.

This is a simplified public overview, not the operational repository or a full deployment kit. All IPs, hostnames, and domains below are fictional examples. The architecture and recovery exercise describe the actual lab; they are not a live health report.

## How it fits together

```mermaid
flowchart TB
    admin["Admin workstation
Terraform and Ansible"] --> cloud
    git["Forgejo
review and validation"] -->|"approved source, run by operator"| admin
    subgraph cloud["Five Linux hosts"]
        os["OpenStack / Kolla-Ansible
KVM, networking, volumes"]
        ceph["External Ceph
local disks on the Linux hosts"]
        os <--> ceph
    end
    os --> lab01["lab-01: repeatable cluster and recovery<br/>3 control planes, 2 workers<br/>kube-vip API endpoint"]
    os --> lab02["lab-02: manual Kubernetes build<br/>3 control planes, 3 workers<br/>Octavia API and ingress endpoints"]
    lab01 -->|"PVC / Cinder CSI"| os
    lab01 -->|"Velero / Kopia backups"| nas["NAS / MinIO<br/>outside both workload clusters"]
    identity["FreeIPA / Keycloak"] -. "directory and SSO" .-> os
    monitoring["Prometheus / Grafana / Alertmanager"] -. "metrics and alerts" .-> cloud
```

The NAS also hosts management services. It is not a Ceph storage node.

## Two Kubernetes labs

Both run as separate VM groups on the same OpenStack and Ceph foundation.

| Lab | Kubernetes nodes | Build approach | API access |
|---|---|---|---|
| lab-01 | 3 control planes, 2 workers | Terraform and Ansible for repeatable provisioning and recovery practice | kube-vip |
| lab-02 | 3 control planes, 3 workers | Terraform creates VMs; Kubernetes is configured separately by hand | Octavia active/standby load balancer |

lab-02 also has an Octavia ingress design that forwards HTTP/HTTPS to Traefik on the workers. Its Terraform module does not install Kubernetes. The completed restore described here belongs to lab-01, not both labs.

## What I use

| Layer | Tools | Purpose |
|---|---|---|
| Private cloud | OpenStack, Kolla-Ansible, KVM | Run VMs and manage networks and volumes |
| Storage | Ceph RBD, Cinder, Cinder CSI | Give VMs and Kubernetes workloads persistent storage |
| Provisioning | Terraform, Ansible, kubeadm | Create cloud resources, then configure guests |
| Kubernetes | kubeadm; Cilium and kube-vip in lab-01 | Practice repeatable and manual cluster builds |
| Load balancing | Octavia, Traefik | lab-02 API access and application ingress |
| Backup | Velero, Kopia, MinIO | Restore application objects and file data |
| Identity | FreeIPA, Keycloak | Central directory and supported application SSO |
| Operations | Prometheus, Grafana, Alertmanager, Forgejo | Observe the lab and review changes |

## Decisions I can explain

- Terraform owns cloud resources. Ansible configures the guests. I keep those jobs separate.
- Kubernetes control-plane VMs use hard anti-affinity so one hypervisor does not host all of them.
- A retained volume is not a backup. I use a separate backup path for application recovery.
- Git validation does not deploy infrastructure. An operator runs the approved source.
- The NAS-hosted management and backup services sit outside both Kubernetes clusters.

This is still one home site with shared power, networking, and a NAS. Multiple controllers do not make it a production disaster-recovery environment. I have completed a small workload restore, not a full clean-room rebuild of every service.

## Read more

- [Design and example addressing](docs/design.md)
- [Completed recovery exercise](docs/recovery.md)
- [Short interview walkthrough](docs/demo.md)
- [Shared foundation inventory](examples/inventory.ini)
- [Both Kubernetes lab inventories](examples/kubernetes-inventory.ini)
- [Example Kubernetes storage class](examples/storageclass.yaml)

The examples are reference material. They contain no credentials, real endpoints, state files, or private Git history. They will not deploy the lab on their own.
