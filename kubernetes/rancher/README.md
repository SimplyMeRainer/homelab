# Dedicated Rancher management VM and native K3s/Helm path

`terraform/rancher-management` produces one **separate** VM, network/router, SSH
public keypair, security group and floating IP, using produced `kit-management`
flavor. It is not one of either workload cluster's nodes, and is not an assumed
unowned machine. This is a single-node learning management plane, **not HA Rancher**.
Back up its K3s datastore, TLS/PKI and Rancher resources independently before upgrades.
Ansible workload-lab baseline guards do not allow this management inventory; use
this native K3s path instead of weakening those guards.

## Native management cluster installation

On its Ubuntu 24.04 amd64 guest, using trusted SSH, install distribution prerequisites
`ca-certificates curl iptables` and ensure correct time, DNS, kernel networking and
swap disabled persistently. K3s brings its own versioned container runtime and CNI;
**do not install workload kubeadm/containerd on this VM**. Version
`v1.35.10+k3s1` and its public amd64 checksum manifest were verified upstream.
Obtain `k3s` and its checksum on the guest, authenticate release provenance according
to your supply-chain policy, then verify the downloaded bytes:

```sh
umask 077
mkdir -p /root/k3s-download
cd /root/k3s-download
curl -fL 'https://github.com/k3s-io/k3s/releases/download/v1.35.10%2Bk3s1/k3s' -o k3s
curl -fL 'https://github.com/k3s-io/k3s/releases/download/v1.35.10%2Bk3s1/sha256sum-amd64.txt' -o sha256sum-amd64.txt
grep '  k3s$' sha256sum-amd64.txt | sha256sum -c -
install -m 0755 k3s /usr/local/bin/k3s
install -d -m 0700 /etc/rancher/k3s
```

Run those privileged commands in a root shell. Copy this directory's
`k3s-config.yaml.example` privately to `/etc/rancher/k3s/config.yaml`, mode0600.
Replace node IP/advertise address from Terraform `nodes`, management floating IP
and real management DNS name/SAN. Pod/service CIDRs must not overlap the lab networks.
Copy `k3s.service` to `/etc/systemd/system/k3s.service`, mode0644, then:

```sh
systemctl daemon-reload
systemctl enable --now k3s
k3s kubectl wait --for=condition=Ready nodes --all --timeout=10m
chmod 600 /etc/rancher/k3s/k3s.yaml
```

Securely copy the generated kubeconfig to the operator's
`runtime/terraform/rancher-management/admin.conf` (mode0600). Edit only its server URL
from loopback to the management floating IP or DNS **already present in the K3s SANs**.
Set KUBECONFIG explicitly, verify context/server, and check node readiness.
The K3s Node token and datastore under `/var/lib/rancher/k3s` are recovery secrets;
never print/copy them into Git. No cluster deploy was run during kit development.

## Native Helm ingress and Rancher installation

Fetch/check Traefik and Rancher archives using `kubernetes/charts.lock.json`. Set DNS
`rancher.lab.example` (replace with your real owned internal domain) to the management
floating IP, and obtain a trusted TLS certificate/key for that exact name. Clients
and downstream cluster nodes must trust that issuing CA; no insecure registration.

```sh
export KUBECONFIG="$PWD/runtime/terraform/rancher-management/admin.conf"
# Set NODE_IP to the exact private address from Terraform nodes output.
helm upgrade --install traefik runtime/charts/traefik-42.3.2.tgz --namespace traefik --create-namespace -f kubernetes/rancher/traefik-values.yaml --set-string ports.websecure.hostIP="$NODE_IP" --wait --timeout 10m
kubectl create namespace cattle-system --dry-run=client -o yaml | kubectl apply -f -
kubectl -n cattle-system create secret tls tls-rancher-ingress --cert=runtime/tls/rancher-fullchain.pem --key=runtime/tls/rancher-key.pem --dry-run=client -o yaml | kubectl apply -f -
kubectl -n cattle-system create secret generic tls-ca --from-file=cacerts.pem=runtime/tls/ca-chain.pem --dry-run=client -o yaml | kubectl apply -f -
helm upgrade --install rancher runtime/charts/rancher-2.15.3.tgz --namespace cattle-system -f kubernetes/rancher/values.yaml --set-string hostname="$RANCHER_HOSTNAME" --wait --timeout 10m
kubectl -n cattle-system rollout status deployment/rancher --timeout=10m
```

Traefik uses a CNI hostPort bound only to the supplied node IP:443, not a public
wildcard bind. Neutron admits 443 only from explicit administrator CIDRs. Extend
those CIDRs narrowly to the source addresses used by downstream cluster agents
before importing clusters; otherwise Rancher will be unreachable from agents.
TLS is externally supplied (`ingress.tls.source=secret`), so cert-manager is not an
implicit dependency. For a public CA use `privateCA=false` and omit `tls-ca`.
The chart creates the initial bootstrap Secret; retrieve it only in a private local
terminal through Rancher's official first-login ceremony, immediately change it,
and configure the intended external identity provider. No password is passed to Helm
or committed. Enable audit/backup policy before trusting this management plane.

Import lab-01 and lab-02 **separately** through Rancher's supported existing-cluster
workflow. Review manifests and CA trust, apply with each lab's explicit kubeconfig,
and verify expected nodes/counts before granting access. The registration manifests
are secret/runtime artifacts; do not publish them. Import does not transfer Terraform
ownership, rebuild a cluster or prove a restore. For HA management build an explicitly
sized separate cluster and migrate through Rancher's documented backup/restore path;
this one-VM baseline does not claim that capability.
