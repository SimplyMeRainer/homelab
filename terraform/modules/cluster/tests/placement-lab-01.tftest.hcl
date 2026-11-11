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
  cluster_name              = "lab-01"
  control_plane_count       = 3
  worker_count              = 2
  api_mode                  = "kube-vip"
  tenant_cidr               = "203.0.113.0/24"
  admin_cidrs               = ["192.0.2.0/24"]
}
run "placement_wiring" {
  command = plan
  assert {
    condition     = length(openstack_compute_servergroup_v2.control_plane) == 1 && openstack_compute_servergroup_v2.control_plane[0].policies == tolist(["anti-affinity"])
    error_message = "Workload control planes require a hard anti-affinity group."
  }
  assert {
    condition     = alltrue([for name, node in openstack_compute_instance_v2.node : local.node_specs[name].role == "control_plane" ? (length(node.scheduler_hints) == 1 && one(node.scheduler_hints).group == openstack_compute_servergroup_v2.control_plane[0].id) : length(node.scheduler_hints) == 0])
    error_message = "Only actual control-plane instances must carry their own group's Nova scheduler hint."
  }
}
