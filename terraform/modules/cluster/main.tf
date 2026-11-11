data "openstack_networking_network_v2" "external" {
  name     = var.external_network_name
  external = true
}
data "openstack_images_image_v2" "ubuntu" {
  name        = var.image_name
  most_recent = false
}
data "openstack_compute_flavor_v2" "control_plane" { name = var.control_plane_flavor_name }
data "openstack_compute_flavor_v2" "worker" { name = var.worker_flavor_name }
locals {
  node_specs = merge(
    { for i in range(var.control_plane_count) : format("%s-cp-%02d", var.cluster_name, i + 1) => { role = "control_plane", index = i + 11 } },
    { for i in range(var.worker_count) : format("%s-worker-%02d", var.cluster_name, i + 1) => { role = "worker", index = i + 21 } }
  )
  vip = cidrhost(var.tenant_cidr, 10)
}
resource "openstack_networking_network_v2" "tenant" { name = "${var.cluster_name}-network" }
resource "openstack_networking_subnet_v2" "tenant" {
  name            = "${var.cluster_name}-subnet"
  network_id      = openstack_networking_network_v2.tenant.id
  cidr            = var.tenant_cidr
  ip_version      = 4
  dns_nameservers = var.dns_nameservers
  allocation_pool {
    start = cidrhost(var.tenant_cidr, 100)
    end   = cidrhost(var.tenant_cidr, 200)
  }
}
resource "openstack_networking_router_v2" "tenant" {
  name                = "${var.cluster_name}-router"
  external_network_id = data.openstack_networking_network_v2.external.id
}
resource "openstack_networking_router_interface_v2" "tenant" {
  router_id = openstack_networking_router_v2.tenant.id
  subnet_id = openstack_networking_subnet_v2.tenant.id
}
resource "openstack_compute_keypair_v2" "admin" {
  name       = "${var.cluster_name}-admin"
  public_key = trimspace(var.ssh_public_key)
}
resource "openstack_networking_secgroup_v2" "nodes" {
  name                 = "${var.cluster_name}-nodes"
  delete_default_rules = true
}
resource "openstack_networking_secgroup_rule_v2" "egress" {
  direction         = "egress"
  ethertype         = "IPv4"
  security_group_id = openstack_networking_secgroup_v2.nodes.id
}
resource "openstack_networking_secgroup_rule_v2" "internal" {
  direction         = "ingress"
  ethertype         = "IPv4"
  remote_group_id   = openstack_networking_secgroup_v2.nodes.id
  security_group_id = openstack_networking_secgroup_v2.nodes.id
}
resource "openstack_networking_secgroup_rule_v2" "ssh" {
  for_each          = var.admin_cidrs
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  remote_ip_prefix  = each.value
  security_group_id = openstack_networking_secgroup_v2.nodes.id
}
resource "openstack_networking_secgroup_rule_v2" "api" {
  for_each          = var.admin_cidrs
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 6443
  port_range_max    = 6443
  remote_ip_prefix  = each.value
  security_group_id = openstack_networking_secgroup_v2.nodes.id
}
resource "openstack_networking_secgroup_rule_v2" "lb" {
  for_each          = var.api_mode == "octavia" ? { api = 6443, http = 30080, https = 30443 } : {}
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = each.value
  port_range_max    = each.value
  remote_ip_prefix  = var.tenant_cidr
  security_group_id = openstack_networking_secgroup_v2.nodes.id
}
resource "openstack_networking_secgroup_rule_v2" "management_https" {
  for_each          = var.api_mode == "standalone" ? var.admin_cidrs : toset([])
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 443
  port_range_max    = 443
  remote_ip_prefix  = each.value
  security_group_id = openstack_networking_secgroup_v2.nodes.id
}
resource "openstack_networking_port_v2" "vip" {
  count              = var.api_mode == "kube-vip" ? 1 : 0
  name               = "${var.cluster_name}-api-reservation"
  network_id         = openstack_networking_network_v2.tenant.id
  security_group_ids = [openstack_networking_secgroup_v2.nodes.id]
  fixed_ip {
    subnet_id  = openstack_networking_subnet_v2.tenant.id
    ip_address = local.vip
  }
}
resource "openstack_networking_port_v2" "node" {
  for_each           = local.node_specs
  name               = each.key
  network_id         = openstack_networking_network_v2.tenant.id
  security_group_ids = [openstack_networking_secgroup_v2.nodes.id]
  fixed_ip {
    subnet_id  = openstack_networking_subnet_v2.tenant.id
    ip_address = cidrhost(var.tenant_cidr, each.value.index)
  }
  dynamic "allowed_address_pairs" {
    for_each = var.api_mode == "kube-vip" && each.value.role == "control_plane" ? [local.vip] : []
    content { ip_address = allowed_address_pairs.value }
  }
}
# Separate module instances produce separate hard placement groups for each lab.
# Standalone Rancher management is deliberately outside workload placement.
resource "openstack_compute_servergroup_v2" "control_plane" {
  count    = var.api_mode == "standalone" ? 0 : 1
  name     = "${var.cluster_name}-control-plane"
  policies = ["anti-affinity"]
}
resource "openstack_compute_instance_v2" "node" {
  for_each  = local.node_specs
  name      = each.key
  image_id  = data.openstack_images_image_v2.ubuntu.id
  flavor_id = each.value.role == "control_plane" ? data.openstack_compute_flavor_v2.control_plane.id : data.openstack_compute_flavor_v2.worker.id
  key_pair  = openstack_compute_keypair_v2.admin.name
  network { port = openstack_networking_port_v2.node[each.key].id }
  dynamic "scheduler_hints" {
    for_each = var.api_mode != "standalone" && each.value.role == "control_plane" ? [openstack_compute_servergroup_v2.control_plane[0].id] : []
    content { group = scheduler_hints.value }
  }
  lifecycle { prevent_destroy = true }
  # Deliberately no cloud-init, provisioner or private key generation.
  depends_on = [openstack_networking_router_interface_v2.tenant]
}
resource "openstack_networking_floatingip_v2" "node" {
  for_each   = local.node_specs
  pool       = data.openstack_networking_network_v2.external.name
  port_id    = openstack_networking_port_v2.node[each.key].id
  depends_on = [openstack_networking_router_interface_v2.tenant]
}
