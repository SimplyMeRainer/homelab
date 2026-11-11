"""Daemonless regression checks; run python3 -m unittest discover -s services/tests -v."""
import json
import pathlib
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class ConfigurationTests(unittest.TestCase):
    def test_compose_has_pinned_persistent_management_services(self):
        self.assertTrue((ROOT / 'compose.yaml').is_file(), 'management Compose configuration is missing')
        import yaml
        config = yaml.safe_load((ROOT / 'compose.yaml').read_text())
        expected = {'forgejo', 'minio', 'vault', 'keycloak', 'postgres', 'prometheus', 'grafana', 'alertmanager', 'n8n'}
        self.assertEqual(set(config['services']), expected)
        for name, service in config['services'].items():
            if name == 'minio':
                self.assertEqual(service['build']['context'], './minio')
                self.assertIn('ADD --checksum=sha256:', (ROOT / 'minio/Dockerfile').read_text())
            else:
                self.assertRegex(service['image'], r'@sha256:[a-f0-9]{64}$', name)
            self.assertTrue(service.get('volumes'), name)
            self.assertFalse(service.get('privileged'), name)
            self.assertNotIn('docker.sock', json.dumps(service), name)
            for port in service.get('ports', []):
                self.assertTrue(port.startswith('${BIND_ADDRESS:?'), port)
        self.assertNotIn('-dev', json.dumps(config['services']['vault']))

if __name__ == '__main__':
    unittest.main()
