variable "octavia_flavor_name" {
  type    = string
  default = "active-standby"
}
resource "openstack_lb_flavorprofile_v2" "active_standby" {
  name          = "${var.octavia_flavor_name}-profile"
  provider_name = "amphora"
  flavor_data   = jsonencode({ loadbalancer_topology = "ACTIVE_STANDBY" })
}
resource "openstack_lb_flavor_v2" "active_standby" {
  name              = var.octavia_flavor_name
  enabled           = true
  flavor_profile_id = openstack_lb_flavorprofile_v2.active_standby.id
}
output "octavia_flavor" {
  value = { id = openstack_lb_flavor_v2.active_standby.id, name = openstack_lb_flavor_v2.active_standby.name }
}
