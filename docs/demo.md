# A short interview walkthrough

## 1. Explain the layers

Start with the README diagram: physical Linux hosts, OpenStack and Ceph, then both Kubernetes labs. Compare lab-01's three control planes/two workers and repeatable setup with lab-02's three control planes/three workers and manual Kubernetes build. Explain kube-vip versus Octavia API access, and point out the shared failure domains.

## 2. Show current state

These commands use a fictional `lab-demo` cloud profile and separate fictional `lab-01-demo` and `lab-02-demo` Kubernetes contexts. Replace them with your own lab profiles and configure credentials locally. Use explicit targets so the demo does not query a work environment by accident.

```sh
openstack --os-cloud lab-demo hypervisor list
openstack --os-cloud lab-demo server list
openstack --os-cloud lab-demo volume list

# Compare both clusters explicitly.
kubectl --context lab-01-demo get nodes -o wide
kubectl --context lab-02-demo get nodes -o wide

# Follow the tested storage path in lab-01.
kubectl --context lab-01-demo get pods -A
kubectl --context lab-01-demo get storageclass
kubectl --context lab-01-demo get pvc,pv -A
```

Show health as it is. If something is unavailable, explain the boundary rather than describing it as healthy because an older test passed.

## 3. Follow one storage request

In lab-01, trace a pod's PVC through Cinder CSI to an OpenStack volume and the Ceph backend. For lab-02, explain the separate Octavia API and ingress paths. Explain why retention and backup solve different problems without assuming both clusters have identical integrations.

## 4. Discuss the recovery exercise

Describe the [completed lab-01 restore](recovery.md), including the data-integrity check and its limits. Do not present it as a lab-02 recovery result or run a destructive drill during the interview.

## Questions worth discussing

- What fails if a controller host is lost?
- Which components still share a failure domain?
- Why split Terraform from guest configuration?
- How would I verify a restore before calling it successful?
- What would need to change before using this design for production?
