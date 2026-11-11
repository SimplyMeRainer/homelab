# A short interview walkthrough

## 1. Explain the layers

Start with the README diagram: physical Linux hosts, OpenStack and Ceph, then Kubernetes VMs. Point out which parts are disposable and where backups live.

## 2. Show current state

These commands use a fictional `lab-demo` cloud profile and Kubernetes context. Replace both with your own lab profiles and configure credentials locally. Use explicit targets so the demo does not query a work environment by accident.

```sh
openstack --os-cloud lab-demo hypervisor list
openstack --os-cloud lab-demo server list
openstack --os-cloud lab-demo volume list

kubectl --context lab-demo get nodes -o wide
kubectl --context lab-demo get pods -A
kubectl --context lab-demo get storageclass
kubectl --context lab-demo get pvc,pv -A
```

Show health as it is. If something is unavailable, explain the boundary rather than describing it as healthy because an older test passed.

## 3. Follow one storage request

Trace a pod's PVC through Cinder CSI to an OpenStack volume and the Ceph backend. Explain why retention and backup solve different problems.

## 4. Discuss the recovery exercise

Describe the [completed restore](recovery.md), including the data-integrity check and its limits. Do not run a destructive drill during the interview.

## Questions worth discussing

- What fails if a controller host is lost?
- Which components still share a failure domain?
- Why split Terraform from guest configuration?
- How would I verify a restore before calling it successful?
- What would need to change before using this design for production?
