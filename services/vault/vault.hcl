ui = true
disable_mlock = false
storage "file" {
  path = "/vault/file"
}
listener "tcp" {
  address = "[::]:8200"
  tls_cert_file = "/run/tls.crt"
  tls_key_file = "/run/tls.key"
  tls_min_version = "tls12"
}
# No dev mode, no plaintext listener, no cloud auto-unseal dependency.
