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
    condition     = module.cluster.octavia_topology.load_balancers == 2 && module.cluster.octavia_topology.listeners == 3 && module.cluster.octavia_topology.api_members == 3 && module.cluster.octavia_topology.ingress_members == 6
    error_message = "Octavia requires separate API/ingress LBs, 3 listeners, 3 CP API and 6 worker ingress memberships."
  }
  assert {
    condition     = length(module.cluster.nodes) == 6
    error_message = "Exact lab topology is required."
  }
  assert {
    condition     = length([for n in values(module.cluster.nodes) : n if n.role == "control_plane"]) == 3
    error_message = "Control-plane count mismatch."
  }
}
