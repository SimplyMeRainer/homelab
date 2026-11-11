# Security and operator boundaries

This kit can configure Linux hosts, consume disks and create cloud resources. Use a disposable lab you control. Publishing or validating it does not authorize a deployment.

## Before running a build

- Replace the fictional addresses, domains, interfaces and device names with your own reviewed inputs. Check that management, tenant, pod and service networks do not overlap.
- Establish SSH host trust and TLS trust first. Do not disable verification to get past a failed check.
- Review explicit OSD devices. Never point storage preparation at an operating-system disk, mounted filesystem or existing data volume.
- Review the saved Terraform plan before applying it. Keep each lab's state separate; do not copy another cluster's state to reuse its configuration.
- Hardware, operating-system installation, routing and a trusted administration path are prerequisites. Existing production hosts are not disposable build targets.

## Credentials and state

Keep real inputs in ignored `config/local/` files. Keep generated material in ignored `runtime/` directories or another protected location. Use restrictive permissions and encrypted backups.

Never commit Terraform state or plans, application passwords, cloud credentials, SSH private keys, kubeconfigs, CA private keys, Vault recovery material or raw operational logs. Ignore rules help prevent accidents; they do not scan content or remove old Git history.

Use native private prompts, encrypted Ansible Vault files and service-supported secret files. Do not paste passwords into chat, issue reports or shell commands. Give backup clients bucket-scoped credentials rather than MinIO root access.

## CI is not deployment

The GitHub workflow has read-only repository permissions and no cloud credentials. Make targets run validation, not infrastructure changes. Run deployment commands yourself from a trusted operator environment after reviewing the inputs and plan.

A provider-mock plan, Ansible syntax check or Compose configuration check does not establish live health. A successful workload restore also does not prove that every layer can be rebuilt from empty hardware.

## Reporting a problem

Report the affected path, expected behavior and a sanitized reproduction. Do not include real endpoint names, credentials, state files or screenshots containing private information. If a secret was committed, revoke it first; deleting the current file does not remove it from history.
