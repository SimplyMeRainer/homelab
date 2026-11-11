terraform {
  backend "local" {}
  required_version = "= 1.16.5"
  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = "= 3.4.0"
    }
  }
}
