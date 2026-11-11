mock_provider "openstack" {}
run "fixed_topology" {
  command = plan
  variables {
    external_network_name     = "public"
    image_name                = "kit-ubuntu-24.04"
    control_plane_flavor_name = "kit-cp"
    worker_flavor_name        = "kit-worker"
    ssh_public_key            = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBfixtureOnlyNotARealPublicKeyfixture"
    admin_cidrs               = ["192.0.2.0/24"]
  }
  assert {
    condition     = length(module.cluster.nodes) == 1
    error_message = "Exact lab topology is required."
  }
  assert {
    condition     = length([for n in values(module.cluster.nodes) : n if n.role == "control_plane"]) == 1
    error_message = "Control-plane count mismatch."
  }
}
