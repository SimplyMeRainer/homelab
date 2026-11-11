mock_provider "openstack" {}
variables {
  external_network_name     = "public"
  image_name                = "kit-ubuntu-24.04"
  control_plane_flavor_name = "kit-cp"
  worker_flavor_name        = "kit-worker"
  ssh_public_key            = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBfixtureOnlyNotARealPublicKeyfixture"
  cluster_name              = "test"
  control_plane_count       = 3
  worker_count              = 2
  api_mode                  = "kube-vip"
  tenant_cidr               = "203.0.113.0/24"
}
run "reject_plain_zero" {
  command = plan
  variables { admin_cidrs = ["0.0.0.0/0"] }
  expect_failures = [var.admin_cidrs]
}
run "reject_padded_zero" {
  command = plan
  variables { admin_cidrs = ["0.0.0.0/00"] }
  expect_failures = [var.admin_cidrs]
}
run "reject_long_zero" {
  command = plan
  variables { admin_cidrs = ["192.0.2.1/000"] }
  expect_failures = [var.admin_cidrs]
}
run "reject_ipv6" {
  command = plan
  variables { admin_cidrs = ["2001:db8::/64"] }
  expect_failures = [var.admin_cidrs]
}
run "reject_ipv6_zero" {
  command = plan
  variables { admin_cidrs = ["::/00"] }
  expect_failures = [var.admin_cidrs]
}
run "reject_malformed" {
  command = plan
  variables { admin_cidrs = ["not-a-cidr"] }
  expect_failures = [var.admin_cidrs]
}
run "reject_bad_prefix" {
  command = plan
  variables { admin_cidrs = ["192.0.2.0/33"] }
  expect_failures = [var.admin_cidrs]
}
run "reject_empty" {
  command = plan
  variables { admin_cidrs = [] }
  expect_failures = [var.admin_cidrs]
}
