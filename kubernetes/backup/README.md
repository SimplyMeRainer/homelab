# Velero + Kopia to NAS-hosted MinIO

Requires a healthy cluster, a NAS MinIO deployment from `services/`, a TLS hostname
reachable from **every node/pod**, trusted issuing CA, clock synchronization and
an independently protected NAS filesystem. The chart is Velero **12.2.4**, application
**1.18.2**. AWS plugin **v1.14.0** is published upstream and its compatibility table
explicitly pairs v1.14.x with Velero v1.18.x. This recipe selects **Kopia filesystem
backups**, not Cinder snapshots. CSI by itself does not move data off Ceph.

On MinIO, create one bucket per cluster (`lab-02-backups` example), a dedicated
non-root service identity, and attach `minio-policy.json` after editing only that
bucket's name. The policy has bucket/object-scoped S3 permissions; no admin API,
other buckets, EC2 actions or NAS shell access. With an authenticated private `mc`
configuration and the `nas` alias already enrolled through the documented service
ceremony, native policy commands are:

```sh
mc mb --ignore-existing nas/lab-02-backups
mc admin policy create nas lab-02-velero kubernetes/backup/minio-policy.json
mc admin policy attach nas lab-02-velero --user "$DEDICATED_MINIO_USER"
```

Creation/enrollment of that identity is a private human ceremony using the MinIO
console or documented service tooling, not a committed password/default access key.
Put its scoped S3 keys in `runtime/terraform/lab-02/velero-credentials` mode0600:
INI section `[default]`, keys `aws_access_key_id` and `aws_secret_access_key`. Obtain
`runtime/terraform/lab-02/minio-ca.pem` from the trusted NAS CA. No insecure TLS flag.

```sh
kubectl create namespace velero --dry-run=client -o yaml | kubectl apply -f -
kubectl -n velero create secret generic velero-cloud-credentials --from-file=cloud=runtime/terraform/lab-02/velero-credentials --dry-run=client -o yaml | kubectl apply -f -
kubectl -n velero create secret generic minio-ca --from-file=ca.crt=runtime/terraform/lab-02/minio-ca.pem --dry-run=client -o yaml | kubectl apply -f -
# Generate once, preserve on upgrades and escrow this unique Kopia password privately.
test -s runtime/terraform/lab-02/kopia-password || openssl rand -base64 48 > runtime/terraform/lab-02/kopia-password
chmod 600 runtime/terraform/lab-02/kopia-password
kubectl -n velero create secret generic velero-repo-credentials --from-file=repository-password=runtime/terraform/lab-02/kopia-password --dry-run=client -o yaml | kubectl apply -f -
helm upgrade --install velero runtime/charts/velero-12.2.4.tgz --namespace velero -f kubernetes/backup/velero-values.yaml --wait --timeout 10m
kubectl -n velero get backupstoragelocations.velero.io
kubectl -n velero rollout status daemonset/node-agent --timeout=10m
```

First privately override `s3Url`, bucket and region to the actual NAS values (keep
TLS verification and CA reference). `checksumAlgorithm: ""` avoids incompatible
S3 checksum extensions on S3-compatible targets. The node agent requires host
access to kubelet volume paths; treat its privileged RBAC/hostPath access as a
security boundary, not an untrusted workload. Set namespace admission exceptions
explicitly if Pod Security blocks it; do not weaken the whole cluster.

Create a nonempty `workload` namespace with a mounted PVC and a known sentinel file;
for databases quiesce writes/use application-native consistent exports or hooks first.
A crash-consistent filesystem copy is not a transactional database backup.

```sh
velero --kubeconfig "$KUBECONFIG" backup create workload-smoke --include-namespaces workload --default-volumes-to-fs-backup --snapshot-volumes=false --wait
velero --kubeconfig "$KUBECONFIG" backup describe workload-smoke --details
velero --kubeconfig "$KUBECONFIG" restore create workload-smoke-restore --from-backup workload-smoke --namespace-mappings workload:restore-drill --wait
velero --kubeconfig "$KUBECONFIG" restore describe workload-smoke-restore --details
kubectl -n restore-drill get pods,pvc
kubectl apply -f kubernetes/backup/schedule.yaml
```

Only enable the schedule after comparing the sentinel hash in the **restored PVC**
and checking application data. Do not overwrite/delete the original namespace to
prove a restore. Retain output and RPO/RTO observations privately. Keep the Kopia
repository password Secret (`velero-repo-credentials`) in encrypted offline custody;
create it with an independently generated password before first backup following
Velero's repository-password guidance, rather than accepting an unrecorded default.
The namespace secret must contain key `repository-password`; create with
`kubectl -n velero create secret generic velero-repo-credentials --from-file=repository-password=PATH_TO_PRIVATE_PASSWORD_FILE`.

For lab-01 use a different bucket, policy, credentials and repository password;
install against its explicit kubeconfig. Backups do not include bare-metal foundation,
NAS OS, cluster etcd/PKI or Rancher state by implication: separately escrow those
assets and perform a documented disaster-recovery drill. NAS snapshots/replication
and offline copies protect against backup deletion by the scoped S3 identity.
