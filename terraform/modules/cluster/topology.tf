# Nonsecret introspection used by native mock-plan tests; resource collections, not fixtures.
output "octavia_topology" {
  value = {
    load_balancers  = length(openstack_lb_loadbalancer_v2.lb)
    listeners       = length(openstack_lb_listener_v2.tcp)
    api_members     = length([for m in values(openstack_lb_member_v2.node) : m if m.protocol_port == 6443])
    ingress_members = length([for m in values(openstack_lb_member_v2.node) : m if contains([30080, 30443], m.protocol_port)])
  }
}
