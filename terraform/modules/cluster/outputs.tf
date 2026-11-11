locals {
  nodes = { for n, spec in local.node_specs : n => {
    role         = spec.role
    id           = openstack_compute_instance_v2.node[n].id
    node_ip      = cidrhost(var.tenant_cidr, spec.index)
    ansible_host = openstack_networking_floatingip_v2.node[n].address
  } }
  api_vip      = var.api_mode == "octavia" ? openstack_lb_loadbalancer_v2.lb["api"].vip_address : var.api_mode == "kube-vip" ? local.vip : cidrhost(var.tenant_cidr, 11)
  api_endpoint = "${local.api_vip}:6443"
}
output "nodes" { value = local.nodes }
output "api_endpoint" { value = local.api_endpoint }
output "api_vip" { value = local.api_vip }
output "ansible_inventory" {
  value = yamlencode({ all = {
    vars = {
      cluster_name = var.cluster_name
      kube_context = "${var.cluster_name}-admin@${var.cluster_name}"
      api_endpoint = local.api_endpoint
      api_vip      = local.api_vip
      pod_cidr     = var.pod_cidr
      service_cidr = var.service_cidr
    }
    children = { for role in ["control_plane", "worker"] : role => {
      hosts = { for n, spec in local.nodes : n => { ansible_host = spec.ansible_host, node_ip = spec.node_ip } if spec.role == role }
    } }
  } })
}
output "ingress_floating_ip" { value = try(openstack_networking_floatingip_v2.lb["ingress"].address, null) }
output "api_floating_ip" { value = try(openstack_networking_floatingip_v2.lb["api"].address, null) }
