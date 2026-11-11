provider "openstack" {} # OS_CLOUD / OS_CLIENT_CONFIG_FILE supplied externally; never credentials in tfvars.
module "cluster" {
  source                    = "../modules/cluster"
  cluster_name              = "lab-02"
  control_plane_count       = 3
  worker_count              = 3
  api_mode                  = "octavia"
  external_network_name     = var.external_network_name
  image_name                = var.image_name
  control_plane_flavor_name = var.control_plane_flavor_name
  worker_flavor_name        = var.worker_flavor_name
  ssh_public_key            = var.ssh_public_key
  admin_cidrs               = var.admin_cidrs
  tenant_cidr               = var.tenant_cidr
  dns_nameservers           = var.dns_nameservers
  pod_cidr                  = var.pod_cidr
  service_cidr              = var.service_cidr
  octavia_flavor_name       = var.octavia_flavor_name
}
