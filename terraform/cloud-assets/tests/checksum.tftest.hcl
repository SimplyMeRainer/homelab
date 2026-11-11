mock_provider "openstack" {}
run "reject_wrong_image_hash" {
  command = plan
  variables {
    image_path   = "tests/fixture.txt"
    image_sha256 = "0000000000000000000000000000000000000000000000000000000000000000"
  }
  expect_failures = [openstack_images_image_v2.ubuntu]
}
