data "openstack_lb_flavor_v2" "active_standby" {
  count = var.api_mode == "octavia" ? 1 : 0
  name  = var.octavia_flavor_name
}
resource "openstack_lb_loadbalancer_v2" "lb" {
  for_each      = var.api_mode == "octavia" ? toset(["api", "ingress"]) : toset([])
  name          = "${var.cluster_name}-${each.key}"
  vip_subnet_id = openstack_networking_subnet_v2.tenant.id
  flavor_id     = data.openstack_lb_flavor_v2.active_standby[0].id
  depends_on    = [openstack_networking_router_interface_v2.tenant]
}
resource "openstack_networking_floatingip_v2" "lb" {
  for_each = openstack_lb_loadbalancer_v2.lb
  pool     = data.openstack_networking_network_v2.external.name
  port_id  = each.value.vip_port_id
}
locals {
  listeners = var.api_mode == "octavia" ? { api = { lb = "api", port = 6443, target = 6443 }, http = { lb = "ingress", port = 80, target = 30080 }, https = { lb = "ingress", port = 443, target = 30443 } } : {}
  members   = merge([for l, spec in local.listeners : { for n, node in local.node_specs : "${l}/${n}" => { listener = l, node = n, port = spec.target } if(l == "api" ? node.role == "control_plane" : node.role == "worker") }]...)
}
resource "openstack_lb_listener_v2" "tcp" {
  for_each        = local.listeners
  name            = "${var.cluster_name}-${each.key}"
  loadbalancer_id = openstack_lb_loadbalancer_v2.lb[each.value.lb].id
  protocol        = "TCP"
  protocol_port   = each.value.port
  allowed_cidrs   = var.admin_cidrs
}
resource "openstack_lb_pool_v2" "tcp" {
  for_each    = local.listeners
  name        = "${var.cluster_name}-${each.key}"
  listener_id = openstack_lb_listener_v2.tcp[each.key].id
  protocol    = "TCP"
  lb_method   = "ROUND_ROBIN"
}
resource "openstack_lb_monitor_v2" "tcp" {
  for_each    = local.listeners
  pool_id     = openstack_lb_pool_v2.tcp[each.key].id
  type        = "TCP"
  delay       = 5
  timeout     = 3
  max_retries = 3
}
resource "openstack_lb_member_v2" "node" {
  for_each      = local.members
  pool_id       = openstack_lb_pool_v2.tcp[each.value.listener].id
  address       = cidrhost(var.tenant_cidr, local.node_specs[each.value.node].index)
  protocol_port = each.value.port
  subnet_id     = openstack_networking_subnet_v2.tenant.id
}
