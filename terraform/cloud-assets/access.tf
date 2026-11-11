data "openstack_identity_auth_scope_v3" "current" {
  name         = "kit-project"
  set_token_id = false
}
resource "openstack_compute_flavor_access_v2" "kit" {
  for_each  = openstack_compute_flavor_v2.kit
  flavor_id = each.value.id
  tenant_id = data.openstack_identity_auth_scope_v3.current.project_id
}
