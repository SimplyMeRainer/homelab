# Working on the kit

Use a development branch and keep real site configuration out of commits. The examples describe editable inputs; generated runtime files are not the source of truth.

## Local setup

Use Python 3.12+, Terraform 1.16.5, Helm, Ansible core 2.20.11, Docker CLI with Compose, OpenSSL and Apache `htpasswd`. Create a virtual environment and install `requirements-dev.txt` and `requirements-galaxy.yml` as shown in the README.

```sh
git switch -c feat/your-change
make test
make validate
```

`make test` runs the component unittest suites. `make validate` adds native Terraform formatting/schema/provider-mock checks, Ansible syntax checks and checksum-locked Helm renders. The service suite runs the real Compose parser without starting containers. Public dependency downloads can occur; neither command needs cloud credentials.

Write a focused failing check before changing executable behavior, then make it pass. Keep new tests in the component's existing test directory. Use inert fixtures and temporary private directories; never make a test depend on a real host, cloud account or cluster.

## Changing shared inputs

- Keep Terraform outputs and the Ansible inventory contract aligned.
- Keep control-plane/worker counts and bootstrap ownership explicit for both labs.
- Update the chart lock, values, bootstrap version and compatibility evidence together when required by an upgrade.
- Retrieve dependency checksums from their real upstream metadata and verify downloaded bytes. Do not fill a missing pin with a plausible value.
- Preserve strict TLS and Ansible SSH trust. Treat native platform trust exceptions as explicit design boundaries, not test bypasses.
- Keep real configuration, credentials, kubeconfigs, state and plans in ignored protected paths.

## Before publishing

Run the checks, inspect every changed and new file, and review the complete outgoing history for secrets. Include new files in review; an unstaged diff does not show their contents. Use an independent source review for security-relevant or cross-layer changes.

Open a pull request and inspect the actual GitHub Actions result for that head. CI validates source and builds the MinIO image in an ephemeral runner; it does not apply Terraform, configure guests or start the management stack in your lab.

A source change is not a deployed fix. Record live qualification separately when an operator later authorizes a staged deployment.
