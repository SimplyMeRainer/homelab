variable "external_network_name" { type = string }
variable "image_name" { type = string }
variable "control_plane_flavor_name" { type = string }
variable "worker_flavor_name" { type = string }
variable "ssh_public_key" {
  type = string
  validation {
    condition     = can(regex("^ssh-(ed25519|rsa) ", var.ssh_public_key))
    error_message = "Supply an existing SSH PUBLIC key, never a private key."
  }
}
variable "admin_cidrs" {
  type = set(string)
  validation {
    condition = length(var.admin_cidrs) > 0 && alltrue([
      for c in var.admin_cidrs : try(cidrnetmask(c) != "0.0.0.0" && tonumber(split("/", c)[1]) > 0, false)
    ])
    error_message = "Explicit valid IPv4 administrator source CIDRs required; every zero-length prefix (including /00) and IPv6 are forbidden."
  }
}
variable "tenant_cidr" {
  type    = string
  default = "192.0.2.0/24"
}
variable "dns_nameservers" {
  type    = list(string)
  default = ["1.1.1.1", "9.9.9.9"]
}
variable "pod_cidr" {
  type    = string
  default = "10.244.0.0/16"
}
variable "service_cidr" {
  type    = string
  default = "10.96.0.0/12"
}
