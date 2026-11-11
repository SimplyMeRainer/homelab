# A short interview walkthrough

## 1. Explain the layers

Start with the README diagram: physical Linux hosts, OpenStack and Ceph, then both Kubernetes labs and the separate management services. Compare lab-01's three control planes/two workers and repeatable setup with lab-02's three control planes/three workers and manual Kubernetes build. Explain kube-vip versus Octavia API access, and the shared failure domains.

## 2. Show the actual code

- `foundation/`: physical inventory, explicit storage devices and native platform deployment.
- `terraform/`: image/flavor producers, VM/network resources and separate cluster state.
- `ansible/`: guest baseline, serialized kubeadm bootstrap and private inventory/kubeconfig handoff.
- `kubernetes/`: manual lab-02 build and storage/backup/Rancher install inputs.
- `services/`: persistent management stack, PKI and identity configuration.

Trace one editable input through its producer and consumer. For example, a Terraform node's private address becomes `node_ip` in Ansible inventory; the floating address is only the SSH access path.

## 3. Show validation without changing the lab

From a prepared development environment:

```sh
make test
make validate
```

Open the actual GitHub Actions result for the revision being discussed. Explain the difference between provider-mock plans, native syntax/schema/configuration checks, image builds and a real deployment. Do not describe a green CI run as proof of cloud health or HA.

## 4. Optionally show current lab state

These read-only commands use fictional cloud/context labels. Replace them and use explicit private kubeconfig files so the demo cannot silently select a work cluster.

```sh
openstack --os-cloud lab-demo hypervisor list
openstack --os-cloud lab-demo server list
openstack --os-cloud lab-demo volume list

kubectl --kubeconfig /path/to/lab-01.kubeconfig --context lab-01-admin@lab-01 get nodes -o wide
kubectl --kubeconfig /path/to/lab-02.kubeconfig --context lab-02-admin@lab-02 get nodes -o wide
```

Show health as it is. For storage, trace a PVC through Cinder CSI to a cloud volume and Ceph. Explain retention versus backup. Describe the [historical lab-01 restore](recovery.md), its data-integrity check and its limits; do not present it as a lab-02 or clean-room kit rebuild result.

Do not run an apply, shutdown, cluster deletion or restore during a screen share.
