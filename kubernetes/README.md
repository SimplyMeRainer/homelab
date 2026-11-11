# Kubernetes native install recipes

`versions.yaml` is the version handoff. `charts.lock.json` records actual chart archive
SHA256 values verified against public upstream indexes and downloaded bytes.
Kubernetes v1.35.10 was verified via its public kubeadm SHA256 endpoint. Workload
cluster counts are fixed by Terraform: lab-01 3+2; lab-02 3+3. Management is separate.

1. Build cloud assets and VMs through `../terraform/README.md`.
2. Run the Ansible baseline; use the Ansible site play only for lab-01.
3. Build lab-02 manually with `lab-02/README.md`.
4. Explicitly install `storage/README.md` and `backup/README.md` on each desired lab.
5. Build the dedicated management VM cluster and Rancher with `rancher/README.md`.

These commands intentionally require operator-edited addresses, trusted external
credentials and real TLS certificates, not committed examples pretending to be usable
secrets. Never point kubectl/Helm at an implicit current context: set a private
`KUBECONFIG` to the intended lab's admin.conf, then verify context and API first.
No live cluster action was executed during development.

## Fetch and validate the locked charts (no cluster access)

From repository root, use a native curl/sha256sum workflow for **each** URL/hash in
`kubernetes/charts.lock.json`, for example Cilium:

```sh
umask 077
mkdir -p runtime/charts
curl -fL https://helm.cilium.io/cilium-1.19.10.tgz -o runtime/charts/cilium-1.19.10.tgz
printf '%s  %s\n' b7252afca3413a33e2b987c954e52441e96979e411e1495ecc6aefe8cd258863 runtime/charts/cilium-1.19.10.tgz | sha256sum -c -
helm template cilium runtime/charts/cilium-1.19.10.tgz --namespace kube-system --kube-version 1.35.10 -f kubernetes/networking/cilium-values.yaml > runtime/cilium-rendered.yaml
```

Use the local checked archive with `helm upgrade --install` in the component instructions.
Render all values with the matching chart; upstream chart schemas are enforced by Helm.
The repeatable offline entrypoint is `bash kubernetes/tests/render.sh`, with `HELM`,
`CHART_DIR` (default `runtime/charts`) and `MANIFEST_DIR` (default `runtime/rendered`)
overrides. It only renders local archives; it never invokes kubectl or contacts a cluster.
Chart hashes pin the manifests/default image versions, not every container-registry tag.
The smoke Pod is additionally pinned by its verified multiarch image manifest digest.
Upgrade charts and Kubernetes only after validating their upstream compatibility and
repeating renders, schema tests and a real staged rollout/restore drill.
