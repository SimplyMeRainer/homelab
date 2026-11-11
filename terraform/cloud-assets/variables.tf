variable "image_path" { type = string }
variable "image_sha256" {
  type = string
  validation {
    condition     = can(regex("^[a-f0-9]{64}$", var.image_sha256))
    error_message = "Supply the SHA256 from the authenticated upstream SHA256SUMS, lowercase hex."
  }
}
variable "image_name" {
  type    = string
  default = "kit-ubuntu-24.04"
}
variable "flavors" {
  type = map(object({ name = string, vcpus = number, ram = number, disk = number }))
  default = {
    cp         = { name = "kit-cp", vcpus = 4, ram = 8192, disk = 60 }
    worker     = { name = "kit-worker", vcpus = 4, ram = 8192, disk = 80 }
    management = { name = "kit-management", vcpus = 4, ram = 16384, disk = 100 }
  }
}
