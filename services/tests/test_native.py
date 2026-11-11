"""Run the real Compose parser using temporary inert inputs; no Docker daemon."""
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class NativeComposeTests(unittest.TestCase):
    def test_generated_secret_web_config_is_valid_yaml(self):
        import yaml
        with tempfile.TemporaryDirectory(prefix='service-secrets-', dir=os.environ.get('TMPDIR')) as tmp:
            out = pathlib.Path(tmp) / 'secrets'
            subprocess.run(['sh',str(ROOT/'secrets.sh'),str(out)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
            config = yaml.safe_load((out/'monitor-web.yml').read_text())
            self.assertIsInstance(config['basic_auth_users'],dict)
            self.assertTrue(config['basic_auth_users']['monitor'].startswith('$2'))
            for f in out.iterdir(): self.assertEqual(f.stat().st_mode & 0o777,0o600)
            self.assertEqual((out/'monitor_password').read_bytes(),(out/'monitor_password_grafana').read_bytes())
            self.assertEqual((out/'grafana_oidc_secret').read_bytes(),(out/'grafana_oidc_secret_grafana').read_bytes())
            self.assertNotEqual((out/'postgres_password').read_bytes(),(out/'keycloak_admin_password').read_bytes())
            self.assertNotIn(b'\n',(out/'ldap_bind_password').read_bytes())
            ldif = pathlib.Path(tmp)/'keycloak-bind.ldif'
            subprocess.run(['sh',str(ROOT/'identity/bind-ldif.sh'),str(ldif),str(out/'ldap_bind_password'),'dc=lab,dc=example'],check=True,capture_output=True)
            import base64
            encoded = next(line.split(':: ',1)[1] for line in ldif.read_text().splitlines() if line.startswith('userPassword:: '))
            self.assertEqual(base64.b64decode(encoded),(out/'ldap_bind_password').read_bytes())
            self.assertEqual(ldif.stat().st_mode & 0o777,0o600)
            # Exercise the real producer: every bad input must fail before output.
            missing = pathlib.Path(tmp)/'missing-secret'
            empty = pathlib.Path(tmp)/'empty-secret'; empty.touch(mode=0o600)
            unreadable = pathlib.Path(tmp)/'unreadable-secret'
            unreadable.write_bytes(b'INERT'); unreadable.chmod(0)
            directory = pathlib.Path(tmp)/'directory-secret'; directory.mkdir(mode=0o700)
            fifo = pathlib.Path(tmp)/'fifo-secret'; os.mkfifo(fifo,0o600)
            for bad in [missing,empty,unreadable,directory,fifo]:
                with self.subTest(secret=bad.name):
                    rejected = pathlib.Path(tmp)/(bad.name+'.ldif')
                    run = subprocess.run(['sh',str(ROOT/'identity/bind-ldif.sh'),str(rejected),str(bad),'dc=lab,dc=example'],capture_output=True,timeout=5)
                    self.assertNotEqual(run.returncode,0)
                    self.assertFalse(rejected.exists())
            # A failing external encoder/read must not be hidden by trailing tr.
            tools = pathlib.Path(tmp)/'tools'; tools.mkdir(mode=0o700)
            encoder = tools/'base64'
            encoder.write_text('#!/bin/sh\nprintf partial\nexit 23\n'); encoder.chmod(0o700)
            env = os.environ.copy(); env['PATH'] = str(tools)+os.pathsep+env['PATH']
            rejected = pathlib.Path(tmp)/'encoder-failure.ldif'
            run = subprocess.run(['sh',str(ROOT/'identity/bind-ldif.sh'),str(rejected),str(out/'ldap_bind_password'),'dc=lab,dc=example'],env=env,capture_output=True,timeout=5)
            self.assertNotEqual(run.returncode,0)
            self.assertFalse(rejected.exists())
            # Existing output identities (including dangling links) are never used.
            for kind in ['regular','symlink','dangling']:
                with self.subTest(output=kind):
                    destination = pathlib.Path(tmp)/(kind+'.ldif')
                    unexpected = pathlib.Path(tmp)/(kind+'-target')
                    if kind == 'regular': destination.write_bytes(b'KEEP')
                    else:
                        if kind == 'symlink': unexpected.write_bytes(b'KEEP')
                        destination.symlink_to(unexpected)
                    run = subprocess.run(['sh',str(ROOT/'identity/bind-ldif.sh'),str(destination),str(out/'ldap_bind_password'),'dc=lab,dc=example'],capture_output=True,timeout=5)
                    self.assertNotEqual(run.returncode,0)
                    if kind == 'regular': self.assertEqual(destination.read_bytes(),b'KEEP')
                    else:
                        self.assertTrue(destination.is_symlink())
                        if kind == 'symlink': self.assertEqual(unexpected.read_bytes(),b'KEEP')
                        else: self.assertFalse(unexpected.exists())
            public_parent = pathlib.Path(tmp)/'public-parent'; public_parent.mkdir(mode=0o755)
            public_parent.chmod(0o755)
            self.assertEqual(public_parent.stat().st_mode & 0o777,0o755)
            run = subprocess.run(['sh',str(ROOT/'identity/bind-ldif.sh'),str(public_parent/'new.ldif'),str(out/'ldap_bind_password'),'dc=lab,dc=example'],capture_output=True,timeout=5)
            self.assertNotEqual(run.returncode,0)
            self.assertFalse((public_parent/'new.ldif').exists())
            # Create a destination after the early check, inside the encoder step.
            # This exercises exclusive shell redirection, not just -e/-L checks.
            native_encoder = shutil.which('base64')
            assert native_encoder is not None
            for kind in ['regular','dangling']:
                with self.subTest(racing_output=kind):
                    destination = pathlib.Path(tmp)/('race-'+kind+'.ldif')
                    unexpected = pathlib.Path(tmp)/('race-'+kind+'-target')
                    encoder.write_text('#!/bin/sh\n'
                        'if [ "$RACE_KIND" = regular ]; then printf KEEP > "$RACE_OUT"; '
                        'else ln -s "$RACE_TARGET" "$RACE_OUT"; fi\n'
                        'exec "$NATIVE_ENCODER"\n')
                    env.update(RACE_KIND=kind,RACE_OUT=str(destination),RACE_TARGET=str(unexpected),NATIVE_ENCODER=native_encoder)
                    run = subprocess.run(['sh',str(ROOT/'identity/bind-ldif.sh'),str(destination),str(out/'ldap_bind_password'),'dc=lab,dc=example'],env=env,capture_output=True,timeout=5)
                    self.assertNotEqual(run.returncode,0)
                    if kind == 'regular': self.assertEqual(destination.read_bytes(),b'KEEP')
                    else:
                        self.assertTrue(destination.is_symlink())
                        self.assertFalse(unexpected.exists())

    def test_native_compose_config_with_inert_files(self):
        docker = shutil.which('docker')
        self.assertIsNotNone(docker, 'Docker CLI + Compose plugin required (daemon NOT required)')
        assert docker is not None
        with tempfile.TemporaryDirectory(prefix='service-compose-', dir=os.environ.get('TMPDIR')) as tmp:
            tmp = pathlib.Path(tmp)
            env = os.environ.copy()
            for line in (ROOT/'management.env.example').read_text().splitlines():
                if line and not line.startswith('#'):
                    key,value = line.split('=',1); env[key] = value
            for key in ['TLS_DIR','SECRET_DIR']:
                path = tmp/key; path.mkdir(mode=0o700); env[key] = str(path)
            env['IDENTITY_CA_FILE'] = str(tmp/'ipa-ca.crt')
            pathlib.Path(env['IDENTITY_CA_FILE']).write_text('INERT PUBLIC CERTIFICATE FIXTURE\n')
            # Parse source natively first; then create every declared secret input.
            import yaml
            source = yaml.safe_load((ROOT/'compose.yaml').read_text())
            for name, entry in source['secrets'].items():
                (pathlib.Path(env['SECRET_DIR'])/name).write_text('INERT-NOT-A-CREDENTIAL\n')
            (pathlib.Path(env['SECRET_DIR'])/'monitor-web.yml').write_text('basic_auth_users: {}\n')
            for name in ['forgejo','minio','vault','keycloak','prometheus','grafana','alertmanager','n8n']:
                for suffix in ['crt','key']:
                    (pathlib.Path(env['TLS_DIR'])/(name+'.'+suffix)).write_text('INERT TLS FIXTURE\n')
            (pathlib.Path(env['TLS_DIR'])/'ca.crt').write_text('INERT PUBLIC CA FIXTURE\n')
            run = subprocess.run([docker,'compose','--project-directory',str(ROOT),'-f',str(ROOT/'compose.yaml'),'config','--format','json'],env=env,capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)
            rendered = json.loads(run.stdout)
            spec = importlib.util.spec_from_file_location('service_validate', ROOT/'validate.py')
            assert spec is not None and spec.loader is not None
            validator = importlib.util.module_from_spec(spec); spec.loader.exec_module(validator)
            validator.check_compose(rendered)
            self.assertEqual(len(rendered['services']),9)
            self.assertNotIn('ports',rendered['services']['postgres'])

if __name__ == '__main__': unittest.main()
