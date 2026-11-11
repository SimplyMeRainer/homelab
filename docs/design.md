# Design notes

## Physical cloud, two virtual workload clusters

The Linux hosts run OpenStack and external Ceph. All five contribute compute capacity and local Ceph storage. Three also have controller roles; two of those handle Neutron network services.

Both Kubernetes labs run in tenant VMs, not on the physical OpenStack hosts. That lets me rebuild either workload cluster without treating the cloud foundation as disposable.

The NAS holds backup objects and management services. It does not supply the Ceph OSDs. Keeping a backup outside the workload cluster helps with recovery, but a single NAS is still a shared failure point.

## lab-01 and lab-02

- **lab-01:** three control planes and two workers, with repeatable Terraform/Ansible provisioning and a kube-vip API endpoint. This is the lab used for the completed storage and recovery exercise. Its registry also includes a separate Rancher management VM, outside the five Kubernetes nodes.
- **lab-02:** three control planes and three workers. Terraform owns the VMs and cloud load balancers; Kubernetes setup is deliberately manual. The API uses an Octavia active/standby load balancer rather than kube-vip. A separate Octavia ingress load balancer forwards HTTP/HTTPS to Traefik's worker NodePorts.

Both have hard anti-affinity for their control-plane VMs. Placement policy is not proof of automatic VM recovery or spare capacity. These are two clusters on one shared foundation, not independent sites. The descriptions cover the design, not a claim that every endpoint is currently healthy.

## Example addressing

These are documentation-only ranges, not working lab addresses. `lab.example` is also a placeholder domain. Do not use this table as a deployment plan.

| Network | Example range | Use |
|---|---|---|
| Management | 192.0.2.0/24 | Hosts, management services, API access |
| Provider | 198.51.100.0/24 | Example floating-IP network |
| Tenant | 203.0.113.0/24 | Example VM network |

| Example name | Example address | Role |
|---|---|---|
| api.lab.example | 192.0.2.10 | OpenStack API virtual IP |
| cloud-01.lab.example | 192.0.2.11 | Control, network, compute, Ceph |
| cloud-02.lab.example | 192.0.2.12 | Control, network, compute, Ceph |
| cloud-03.lab.example | 192.0.2.13 | Control, compute, Ceph |
| cloud-04.lab.example | 192.0.2.14 | Compute, Ceph |
| cloud-05.lab.example | 192.0.2.15 | Compute, Ceph |
| store-01.lab.example | 192.0.2.40 | NAS and management services |
| id-01.lab.example | 192.0.2.41 | Directory-service VM on the NAS |

The [Kubernetes inventory](../examples/kubernetes-inventory.ini) uses fictional `learn-*` names for lab-01 and `study-*` names for lab-02, in the example tenant range above. Those are separate from the physical `cloud-*` hosts.

| Lab | Fictional API name | Example internal VIP | Node addresses |
|---|---|---|---|
| lab-01 | api-a.lab.example | 203.0.113.20 | Control planes .21–.23; workers .31–.32 |
| lab-02 | api-b.lab.example | 203.0.113.100 | Control planes .101–.103; workers .111–.113 |

All abbreviated addresses in this table are within `203.0.113.0/24`. API VIPs are endpoints, not additional Kubernetes nodes. The comparison does not imply separate tenant subnets.

## Networking

Management, provider access, and tenant traffic have different jobs. Neutron handles tenant networking and floating IPs; the physical network handles routing between the lab segments.

One lesson from the provider network: apply a VLAN tag at one layer. If a host VLAN interface supplies the tag, configuring the same tag again in Neutron can break traffic.

## Storage path

The verified lab-01 workload used this path; the sample storage class is not evidence that lab-02 has the same integrations installed.

```text
Pod -> PVC -> Cinder CSI -> Cinder volume -> Ceph RBD
```

The sample storage class uses `Retain` to keep the cloud volume after a claim is released, and `WaitForFirstConsumer` to delay provisioning until scheduling. Retention needs a cleanup plan; it does not provide point-in-time recovery.

Ceph replication handles some disk and host failures. Velero and Kopia provide a separate application-backup path. Neither removes the shared power and network risks of a home lab.
