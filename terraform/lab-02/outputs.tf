output "nodes" { value = module.cluster.nodes }
output "api_endpoint" { value = module.cluster.api_endpoint }
output "api_vip" { value = module.cluster.api_vip }
output "ansible_inventory" { value = module.cluster.ansible_inventory }
output "ingress_floating_ip" { value = module.cluster.ingress_floating_ip }
output "api_floating_ip" { value = module.cluster.api_floating_ip }
