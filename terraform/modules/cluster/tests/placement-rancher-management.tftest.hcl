mock_provider "openstack" {
  mock_resource "openstack_compute_servergroup_v2" {
    defaults        = { id = "fixture-control-plane-group" }
    override_during = plan
  }
}
variables {
  external_network_name     = "public"
  image_name                = "kit-ubuntu-24.04"
  control_plane_flavor_name = "kit-cp"
  worker_flavor_name        = "kit-worker"
  ssh_public_key            = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBfixtureOnlyNotARealPublicKeyfixture"
  cluster_name              = "rancher-management"
  control_plane_count       = 1
  worker_count              = 0
  api_mode                  = "standalone"
  tenant_cidr               = "203.0.113.0/24"
  admin_cidrs               = ["192.0.2.0/24"]
}
run "placement_wiring" {
  command = plan
  assert {
    condition     = length(openstack_compute_servergroup_v2.control_plane) == 0 && alltrue([for node in values(openstack_compute_instance_v2.node) : length(node.scheduler_hints) == 0])
    error_message = "Standalone management is not a workload HA group."
  }
}
