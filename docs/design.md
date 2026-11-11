# Design decisions

## One cloud, two workload clusters

Five Linux hosts provide compute and external Ceph storage. Three have OpenStack controller roles and two also handle Neutron network services. The NAS/management host is not a Ceph OSD.

The kit gives lab-01, lab-02 and the separate Rancher management VM independent Terraform roots and state. Both workload clusters still depend on the same physical cloud, power and network. Separate clusters are not independent disaster-recovery sites.

| Lab | Nodes | Learning path | API |
|---|---|---|---|
| lab-01 | 3 control planes, 2 workers | Repeatable Ansible/kubeadm bootstrap and recovery practice | kube-vip private VIP |
| lab-02 | 3 control planes, 3 workers | Terraform infrastructure, manual Kubernetes construction | Octavia active/standby |

lab-02 has a separate Octavia ingress endpoint forwarding to Traefik worker NodePorts. Rancher runs on its own management VM/cluster rather than inside a workload cluster it is meant to manage.

## Native ownership boundaries

Terraform owns cloud resources. Ansible configures hosts and bootstraps lab-01. Native Kolla/cephadm own their platform responsibilities, and native Helm/kubectl recipes install cluster integrations. There is no custom Python provisioning framework or CI deployment identity.

Each producer documents the next consumer's files or resource names. Runtime passwords, cloud credentials, state, saved plans, join credentials, PKI keys and kubeconfigs are not source files.

## Networking

Management, provider access, tenant networks, pods and services have different roles. Replace the fictional examples with a coherent nonoverlapping plan. The kit's independently editable examples are not a live allocation registry.

A provider VLAN tag belongs at one layer. The foundation's documented NIC/provider model must match the switch; do not add the same tag in both a host VLAN child and Neutron.

Private Kubernetes API endpoints need routed administration access. Floating-IP SSH alone is insufficient. API certificates must cover the endpoint clients actually use.

## Storage and recovery

```text
Pod -> PVC -> Cinder CSI -> Cinder volume -> Ceph RBD
```

`Retain` preserves a released backing volume until deliberate cleanup. It does not recover an earlier version of data. Ceph replication handles some storage/host failures; Velero/Kopia provide a separate application-backup path to NAS-hosted MinIO.

Management and backup outside the workload clusters reduce circular recovery dependencies. They remain shared failure points. The [historical lab-01 restore](recovery.md) tested a small workload, not a clean-room reconstruction of this kit.
