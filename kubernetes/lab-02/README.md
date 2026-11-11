# Lab-02: manual kubeadm, three control planes and three workers

This is **not** an automated lab-02 install. Terraform owns VMs/network/LBs only;
Ansible `baseline.yml` is permitted, but not its lab-01-only `site.yml`. A prepared
baseline means Ubuntu 24.04, swap off, synchronized clocks, containerd with systemd
cgroups, IPv4 forwarding, required kernel modules and kubeadm/kubelet/kubectl
**1.35.10** installed/held from the v1.35 upstream repository. Use the shared Ansible
baseline rather than silently substituting a different runtime version.

Before bootstrap inspect `terraform output nodes`, `api_vip`, `api_floating_ip`,
`api_endpoint`, `ingress_floating_ip`. Record the exact mapping privately. Establish
SSH host trust out-of-band. API admin access needs routed tenant/VPN connectivity.
Ensure Neutron metadata is reachable from guests and that Octavia's two Amphorae per
LB land in a failure-tolerant placement; Terraform flavor intent is not failover proof.

## First control plane

On cp-01 (through trusted SSH), copy `kubeadm-init.yaml` to `/root/kubeadm-init.yaml`,
mode 0600. Replace **every** REPLACE value and example address/name with that node's
actual Terraform values. API endpoint is the private Octavia API VIP plus :6443,
**not** the ingress VIP. Add private VIP and API floating IP to certSANs before init.
Match pod/service CIDRs to Terraform inventory; defaults are illustrative RFC1918,
not copied infrastructure values. Do not skip kube-proxy with the supplied Cilium.

```sh
sudo kubeadm config validate --config /root/kubeadm-init.yaml
sudo kubeadm config images pull --config /root/kubeadm-init.yaml
sudo kubeadm init --config /root/kubeadm-init.yaml > /root/kubeadm-init.log 2>&1
sudo chmod 600 /root/kubeadm-init.log /etc/kubernetes/admin.conf
```

Run this in a root shell with umask 077; init log contains short-lived join material.
Do not paste its contents into tickets. Copy admin.conf by trusted SSH to the
operator's private `runtime/terraform/lab-02/admin.conf`; chmod 0600. Set
`KUBECONFIG` to its absolute path and verify the endpoint/context locally before
contacting the API. The admin workstation must route the canonical private API VIP.

## Cilium

Fetch/check the exact charts through `../README.md`. On the operator workstation:

```sh
export KUBECONFIG="$PWD/runtime/terraform/lab-02/admin.conf"
kubectl config view --minify
helm upgrade --install cilium runtime/charts/cilium-1.19.10.tgz --namespace kube-system -f kubernetes/networking/cilium-values.yaml --wait --timeout 10m
kubectl -n kube-system rollout status daemonset/cilium --timeout=10m
```

Cilium uses kube-controller-manager's node PodCIDRs (`ipam.mode=kubernetes`), VXLAN
and the default kube-proxy. Internal cluster security-group traffic permits VXLAN
UDP8472. No external cloud-controller-manager is assumed or installed.

## Join cp-02/cp-03, then all three workers

On cp-01 in a **root shell** (no shell tracing), create protected short-lived values:

```sh
umask 077
kubeadm token create --ttl 30m > /root/join-token
openssl x509 -pubkey -in /etc/kubernetes/pki/ca.crt | openssl pkey -pubin -outform DER | openssl dgst -sha256 -hex > /root/ca-public-hash
kubeadm certs certificate-key > /root/certificate-key
kubeadm init phase upload-certs --upload-certs --certificate-key "$(cat /root/certificate-key)" > /root/upload-certs.log 2>&1
```

The hash value is public, but tokens and certificate key are secrets. Transfer through
trusted SSH into root-owned mode0600 join configs, not a shared terminal/log. Copy
`kubeadm-join.yaml.example` to `/root/join.yaml` on each joining VM. Set node name,
private IP, endpoint, actual token and the hex CA hash (with `sha256:` prefix).
For cp-02/03 add the shown `controlPlane` block with their own advertiseAddress and
the uploaded certificate key; omit that block entirely for each worker. Run serially:

```sh
sudo kubeadm config validate --config /root/join.yaml
sudo kubeadm join --config /root/join.yaml > /root/kubeadm-join.log 2>&1
sudo chmod 600 /root/kubeadm-join.log
```

Wait for each CP to become Ready before the next. After joining:

```sh
kubectl wait --for=condition=Ready nodes --all --timeout=10m
kubectl label node lab-02-worker-01 lab-02-worker-02 lab-02-worker-03 node-role.kubernetes.io/worker=
kubectl get nodes -o wide
kubectl get --raw='/readyz?verbose'
```

Names above are exact Terraform-produced defaults. Revoke the join token on cp-01
with `kubeadm token delete` using its token ID, then securely remove private join
files/key/logs after the ceremony; uploaded certificates expire. Keep the CA/admin
kubeconfig in your encrypted recovery store, not Git.

## Separate ingress LB -> worker NodePorts -> Traefik

```sh
helm upgrade --install traefik runtime/charts/traefik-42.3.2.tgz --namespace traefik --create-namespace -f kubernetes/networking/traefik-values.yaml --wait --timeout 10m
kubectl -n traefik get pods,service -o wide
```

Terraform ingress listeners TCP80/443 forward to **workers only** on 30080/30443.
The API listener TCP6443 forwards to CPs only. Traefik NodePort service uses Cluster
traffic policy, so any healthy worker can forward to a scheduled replica. Create
application TLS secrets and Ingress objects using `ingressClassName: traefik`; point
DNS at `ingress_floating_ip`. No automatic public wildcard ingress, dashboard or
certificate bypass is enabled. Listener allowed_cidrs starts with admin CIDRs.

Finally install `../storage/README.md`, `../backup/README.md` explicitly. Validate
three CPs/three workers, API readyz, DNS, cross-node pod connectivity, Octavia health,
CSI scheduling and a file-backed restore before calling the cluster usable. Perform
one-node-at-a-time failure tests only under a maintenance plan; TCP monitors alone
are not Kubernetes readiness or a tested HA guarantee.
