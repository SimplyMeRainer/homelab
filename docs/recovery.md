# A recovery exercise I completed in lab-01

In lab-01, I backed up a small Kubernetes workload with persistent file data, restored it, and checked the restored file against its original SHA-256 digest. This exercise was not a lab-02 restore test.

This exercise predates the development kit in this repository. It is not evidence that this exact source was deployed from empty hardware.

The workload used a PVC backed by Cinder and Ceph. Velero saved the Kubernetes objects, Kopia backed up the file data, and MinIO on the NAS held the backup.

## What I checked

1. The source workload could read the test file.
2. The backup completed.
3. The restore created the workload and a new backing volume.
4. The restored pod could read the file.
5. The restored file's digest matched the original.

This proved a small application restore through that storage and backup path. It did not prove that every service can be rebuilt from an empty environment, or establish a recovery-time target.

## What I took from it

A running pod is not enough evidence of recovery. I need to check the application's data too.

I also keep the backup repository outside the cluster being rebuilt. Otherwise the recovery process can depend on the system it is supposed to recover.

For an interview, I explain the completed exercise and use read-only checks. I do not delete a cluster or restore over a running workload during a screen share.
