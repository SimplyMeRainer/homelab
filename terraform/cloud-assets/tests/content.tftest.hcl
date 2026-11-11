mock_provider "openstack" {}
run "content_digest_is_lifecycle_input" {
  command = plan
  variables {
    image_path   = "tests/fixture.txt"
    image_sha256 = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
  }
  assert {
    condition     = terraform_data.image_content.triggers_replace == filesha256("tests/fixture.txt")
    error_message = "Actual source bytes must participate in the image replacement lifecycle."
  }
}
