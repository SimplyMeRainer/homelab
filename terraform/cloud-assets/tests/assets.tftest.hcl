mock_provider "openstack" {}
run "native_flavors" {
  command = plan
  variables {
    image_path   = "tests/fixture.txt"
    image_sha256 = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
  }
  assert {
    condition     = openstack_lb_flavorprofile_v2.active_standby.flavor_data == jsonencode({ loadbalancer_topology = "ACTIVE_STANDBY" })
    error_message = "Octavia must use an explicit ACTIVE_STANDBY Amphora flavor profile."
  }
  assert {
    condition     = length(openstack_compute_flavor_access_v2.kit) == 3
    error_message = "Every private flavor must be granted to the provisioning project."
  }
  assert {
    condition     = length(openstack_compute_flavor_v2.kit) == 3
    error_message = "cloud-assets must produce CP, worker and management flavors"
  }
}
