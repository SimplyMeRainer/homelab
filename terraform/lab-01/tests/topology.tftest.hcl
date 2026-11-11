# All provider behavior is mocked: apply below does NOT contact OpenStack.
mock_provider "openstack" {}
variables {
  external_network_name     = "public"
  image_name                = "kit-ubuntu-24.04"
  control_plane_flavor_name = "kit-cp"
  worker_flavor_name        = "kit-worker"
  ssh_public_key            = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBfixtureOnlyNotARealPublicKeyfixture"
  admin_cidrs               = ["192.0.2.0/24"]
}
run "inventory_contract" {
  command = apply
  assert {
    condition     = length(yamldecode(output.ansible_inventory).all.children.control_plane.hosts) == 3 && length(yamldecode(output.ansible_inventory).all.children.worker.hosts) == 2
    error_message = "Ansible inventory must preserve the 3+2 role contract."
  }
  assert {
    condition     = yamldecode(output.ansible_inventory).all.vars.cluster_name == "lab-01" && yamldecode(output.ansible_inventory).all.vars.kube_context == "lab-01-admin@lab-01" && yamldecode(output.ansible_inventory).all.vars.api_endpoint == "203.0.113.10:6443"
    error_message = "Ansible inventory identity/endpoint handoff differs from contract."
  }
  assert {
    condition     = alltrue([for n in values(yamldecode(output.ansible_inventory).all.children.control_plane.hosts) : can(n.node_ip) && can(n.ansible_host)])
    error_message = "Each inventory host needs floating ansible_host and private node_ip."
  }
}
run "five_nodes_and_inventory" {
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
    condition     = length(module.cluster.nodes) == 5
    error_message = "lab-01 must produce exactly three control planes and two workers"
  }
}
