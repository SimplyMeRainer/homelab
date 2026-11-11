# Cinder CSI with externally scoped cloud credentials

Use after the selected cluster is Ready; this is **not assumed installed on lab-02**.
Cinder/Glance/Nova/Keystone and metadata must be healthy, HTTPS trusted, with a usable
cloud default volume type and sufficient quota. The driver version v1.35.0 matches
the Kubernetes minor. The actual verified Helm archive is `openstack-cinder-csi-2.35.0.tgz`.

Create a dedicated project-scoped Keystone application credential for this cluster's
CSI identity. Grant only cloud policy roles needed for Cinder volume create/read/
attach/detach/delete and Nova instance/attachment lookup, not administrator privileges.
Cloud role names/policy differ; verify permissions with your cloud administrator.
A project member credential can affect other project volumes: use a dedicated lab
project if hard tenant isolation is needed. Never reuse Terraform's administrator.

Create `runtime/terraform/lab-02/cloud.conf` mode0600 from `cloud.conf.example`, inserting
that application's actual ID/secret, trusted Keystone URL and region. Obtain the
cloud CA bundle through a trusted channel and store it as private
`runtime/terraform/lab-02/openstack-ca.pem`; never use `insecure=true`.

The chart includes the CSI snapshotter sidecar even though Velero below uses Kopia.
Install its matching **v8.4.0** API/controller prerequisites once per cluster first.
The exact downloaded manifest hashes/URLs are in `supplemental-artifacts.lock.json`;
fetch and check those bytes before applying (do not use a moving branch):

```sh
SNAPSHOT_BASE=https://raw.githubusercontent.com/kubernetes-csi/external-snapshotter/v8.4.0
kubectl apply -f "$SNAPSHOT_BASE/client/config/crd/snapshot.storage.k8s.io_volumesnapshotclasses.yaml"
kubectl apply -f "$SNAPSHOT_BASE/client/config/crd/snapshot.storage.k8s.io_volumesnapshotcontents.yaml"
kubectl apply -f "$SNAPSHOT_BASE/client/config/crd/snapshot.storage.k8s.io_volumesnapshots.yaml"
kubectl apply -f "$SNAPSHOT_BASE/deploy/kubernetes/snapshot-controller/rbac-snapshot-controller.yaml"
kubectl apply -f "$SNAPSHOT_BASE/deploy/kubernetes/snapshot-controller/setup-snapshot-controller.yaml"
```

From repository root, with the correct explicit KUBECONFIG:

```sh
kubectl -n kube-system create secret generic cinder-csi-cloud-config --from-file=cloud.conf=runtime/terraform/lab-02/cloud.conf --dry-run=client -o yaml | kubectl apply -f -
kubectl -n kube-system create configmap openstack-ca --from-file=ca-bundle.crt=runtime/terraform/lab-02/openstack-ca.pem --dry-run=client -o yaml | kubectl apply -f -
```

No CCM is installed by these recipes. Set provider IDs explicitly using the exact Nova
resource IDs in Terraform's `nodes` output, before CSI is installed. This native
shell/jq command consumes that producer output; it does not discover or guess UUIDs:

```sh
terraform -chdir=terraform/lab-02 output -state=../../runtime/terraform/lab-02/terraform.tfstate -json nodes > runtime/terraform/lab-02/nodes.json
jq -r 'to_entries[] | [.key, .value.id] | @tsv' runtime/terraform/lab-02/nodes.json | while IFS="$(printf '\t')" read -r node id; do
  kubectl patch node "$node" --type merge -p "{\"spec\":{\"providerID\":\"openstack:///$id\"}}"
done
helm upgrade --install cinder-csi runtime/charts/openstack-cinder-csi-2.35.0.tgz --namespace kube-system -f kubernetes/storage/cinder-values.yaml --wait --timeout 10m
kubectl apply -f kubernetes/storage/storageclass.yaml
kubectl -n kube-system rollout status daemonset/openstack-cinder-csi-nodeplugin --timeout=10m
kubectl apply -f kubernetes/storage/smoke-pvc.yaml
kubectl wait --for=condition=Ready pod/cinder-smoke --timeout=10m
kubectl get pvc cinder-smoke
```

The image metadata endpoint must supply real instance topology if requested by the
driver; verify metadata from every guest. StorageClass uses the cloud default volume
type and `WaitForFirstConsumer`. The PVC binds only when its consumer schedules.
`Retain` means deleting the PVC does not destroy the underlying Cinder volume: reconcile
and explicitly clean retained test volumes through an approved storage lifecycle.
The smoke Pod proves mount/scheduling only, not file durability or disaster recovery.

For lab-01 repeat with its own nodes output, dedicated app credential and kubeconfig;
override `--set clusterID=lab-01`. Do not share CSI cloud secrets across projects.
Kopia file backup in `../backup` is independent of Cinder snapshots. The VolumeSnapshot
APIs/controller prerequisites do not create a snapshot schedule or a Velero CSI data
mover; do not claim snapshot backups from this default recipe. Never treat Ceph replication as backup.
