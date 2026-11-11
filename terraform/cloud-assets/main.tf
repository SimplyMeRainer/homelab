provider "openstack" {}
# Hash the actual file, not just the operator's claimed checksum. Content changes
# at an unchanged path must replace Glance; prevent_destroy requires review first.
resource "terraform_data" "image_content" {
  triggers_replace = filesha256(pathexpand(var.image_path))
}
resource "openstack_images_image_v2" "ubuntu" {
  name             = var.image_name
  local_file_path  = pathexpand(var.image_path)
  container_format = "bare"
  disk_format      = "qcow2"
  visibility       = "private"
  properties       = { os_distro = "ubuntu", os_version = "24.04", hw_disk_bus = "scsi", hw_scsi_model = "virtio-scsi" }
  lifecycle {
    prevent_destroy      = true
    replace_triggered_by = [terraform_data.image_content]
    precondition {
      condition     = filesha256(pathexpand(var.image_path)) == var.image_sha256
      error_message = "Local cloud image SHA256 differs from the authenticated upstream checksum; upload refused."
    }
  }
}
resource "openstack_compute_flavor_v2" "kit" {
  for_each  = var.flavors
  name      = each.value.name
  vcpus     = each.value.vcpus
  ram       = each.value.ram
  disk      = each.value.disk
  is_public = false
  lifecycle { prevent_destroy = true }
}
output "image" {
  value = { id = openstack_images_image_v2.ubuntu.id, name = openstack_images_image_v2.ubuntu.name, sha256 = terraform_data.image_content.triggers_replace }
}
output "flavors" { value = { for k, f in openstack_compute_flavor_v2.kit : k => { id = f.id, name = f.name } } }
