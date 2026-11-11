#!/usr/bin/env bash
# Offline only: exact local checked chart archives; no kubectl or cluster calls.
set -euo pipefail
umask 077
HELM=${HELM:-helm}
CHART_DIR=${CHART_DIR:-runtime/charts}
MANIFEST_DIR=${MANIFEST_DIR:-runtime/rendered}
mkdir -p "$MANIFEST_DIR"
chmod 700 "$MANIFEST_DIR"
render() {
  "$HELM" template "$1" "$CHART_DIR/$2-$3.tgz" --namespace "$4" --kube-version 1.35.10 -f "kubernetes/$5" > "$MANIFEST_DIR/$6.yaml"
  printf 'PASS %s\n' "$5"
}
render cilium cilium 1.19.10 kube-system networking/cilium-values.yaml cilium
render cinder-csi openstack-cinder-csi 2.35.0 kube-system storage/cinder-values.yaml cinder
render velero velero 12.2.4 velero backup/velero-values.yaml velero
render traefik traefik 42.3.2 traefik networking/traefik-values.yaml traefik
render rancher rancher 2.15.3 cattle-system rancher/values.yaml rancher
render traefik traefik 42.3.2 traefik rancher/traefik-values.yaml management-traefik
