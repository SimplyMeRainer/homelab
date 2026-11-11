"""Real openssl PKI generation and negative validation, no daemon or deployment."""
import importlib.util
import json
import os
import pathlib
import stat
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class SecurityTests(unittest.TestCase):
    def load_validator(self):
        self.assertTrue((ROOT / 'validate.py').is_file(), 'security validator is missing')
        spec = importlib.util.spec_from_file_location('service_validate', ROOT / 'validate.py')
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_rejects_exposed_bind_and_vault_dev_mode(self):
        validate = self.load_validator()
        safe = {'services': {'vault': {'ports': [{'host_ip':'192.0.2.40','published':'8200','target':8200}], 'command':['server']}}}
        validate.check_compose(safe)
        for address in ['0.0.0.0', '::', '', None]:
            safe['services']['vault']['ports'][0]['host_ip'] = address
            with self.assertRaises(ValueError): validate.check_compose(safe)
        safe['services']['vault']['ports'][0]['host_ip'] = '192.0.2.40'
        safe['services']['vault']['command'] = ['server', '-dev']
        with self.assertRaises(ValueError): validate.check_compose(safe)

    def test_pki_has_ca_constraints_hostname_san_and_rejects_key_permissions(self):
        self.assertTrue((ROOT / 'pki.sh').is_file(), 'native PKI script is missing')
        with tempfile.TemporaryDirectory(prefix='service-pki-', dir=os.environ.get('TMPDIR')) as tmp:
            target = pathlib.Path(tmp) / 'pki'
            subprocess.run(['sh', str(ROOT / 'pki.sh'), str(target), 'lab.example'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            validate = self.load_validator()
            validate.check_keys(target)
            ca = subprocess.check_output(['openssl','x509','-in',str(target/'ca.crt'),'-text','-noout'],text=True)
            leaf = subprocess.check_output(['openssl','x509','-in',str(target/'vault.crt'),'-text','-noout'],text=True)
            self.assertIn('CA:TRUE, pathlen:0', ca)
            self.assertIn('Certificate Sign', ca)
            self.assertIn('CA:FALSE', leaf)
            self.assertIn('DNS:vault.lab.example', leaf)
            self.assertIn('TLS Web Server Authentication', leaf)
            subprocess.run(['openssl','verify','-CAfile',str(target/'ca.crt'),str(target/'vault.crt')],check=True,stdout=subprocess.DEVNULL)
            self.assertEqual(stat.S_IMODE((target/'vault.key').stat().st_mode),0o600)
            (target/'vault.key').chmod(0o644)
            with self.assertRaises(ValueError): validate.check_keys(target)
            result = subprocess.run(['sh',str(ROOT/'pki.sh'),str(target),'lab.example'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            self.assertNotEqual(result.returncode,0,'must not overwrite an existing CA')
            for kind in ['directory','fifo','symlink']:
                with self.subTest(key_object=kind):
                    invalid = pathlib.Path(tmp)/kind; invalid.mkdir(mode=0o700)
                    key = invalid/'vault.key'
                    if kind == 'directory': key.mkdir(mode=0o600)
                    elif kind == 'fifo': os.mkfifo(key,0o600)
                    else: key.symlink_to(target/'ca.key')
                    # check_keys must inspect type, never read/open the FIFO.
                    with self.assertRaises(ValueError): validate.check_keys(invalid)

if __name__ == '__main__': unittest.main()
