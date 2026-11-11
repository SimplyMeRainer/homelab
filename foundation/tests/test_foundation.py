"""Offline source/render contracts; never contact infrastructure."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RenderContract(unittest.TestCase):
    def test_native_render_produces_full_inventory_and_safe_globals(self):
        self.assertTrue((ROOT / 'render.yml').is_file(), 'missing native Ansible configuration producer')
        ansible = os.environ.get('ANSIBLE_PLAYBOOK', shutil.which('ansible-playbook') or '')
        self.assertTrue(ansible, 'ansible-playbook required')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'runtime'
            result = subprocess.run([ansible, '-i', 'localhost,', '-c', 'local', str(ROOT / 'render.yml'), '-e', '@' + str(ROOT / 'vars.example.yml'), '-e', 'foundation_runtime=' + str(out)], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            inv = out / 'inventory.ini'
            inventory = subprocess.run([ansible.replace('ansible-playbook', 'ansible-inventory'), '-i', str(inv), '--list'], text=True, capture_output=True)
            self.assertEqual(inventory.returncode, 0, inventory.stderr)
            data = json.loads(inventory.stdout)
            self.assertEqual(len(data['compute']['hosts']), 5)
            self.assertEqual(len(data['control']['hosts']), 3)
            self.assertEqual(len(data['network']['hosts']), 2)
            for group in ('kolla_toolbox', 'kolla_logs', 'cinder-volume', 'loadbalancer', 'nova-conductor', 'ceph'):
                self.assertIn(group, data)
            text = (out / 'kolla/globals.yml').read_text()
            self.assertIn('kolla_enable_tls_internal: "yes"', text)
            self.assertIn('ceph_glance_user: "glance"', text)
            self.assertNotIn('password:', text)
            self.assertEqual((out.stat().st_mode & 0o777), 0o700)
            self.assertEqual((out / 'kolla/globals.yml').stat().st_mode & 0o777, 0o600)
            commands = (out / 'kolla-commands.sh').read_text()
            positions = [commands.index('kolla-ansible ' + c) for c in ('bootstrap-servers', 'prechecks', 'deploy', 'post-deploy')]
            self.assertEqual(positions, sorted(positions))
            self.assertIn('ALLOW_KOLLA_DEPLOY', commands)
            self.assertEqual(data['network']['hosts'], ['node01', 'node02'])
            self.assertIn('enable_octavia: "yes"', text)
            self.assertIn('enable_valkey: "yes"', text)
            self.assertEqual(data['valkey']['children'], ['control'])
            self.assertIn('octavia_auto_configure: "yes"', text)
            self.assertIn('octavia_network_type: tenant', text)
            for name in ('amphora-build.sh', 'octavia-certificates.py', 'amphora-register.sh', 'octavia-register.yml', 'provider-assets.sh'):
                self.assertTrue((out / name).is_file(), 'missing native Octavia producer: ' + name)
            self.assertIn('tasks_from: register', (out / 'octavia-register.yml').read_text())
            self.assertIn('diskimage-create.sh', (out / 'amphora-build.sh').read_text())
            self.assertIn('-passout', (out / 'octavia-certificates.py').read_text())
            self.assertNotIn('pass:', (out / 'octavia-certificates.py').read_text())
            self.assertIn('heartbeat_key', (out / 'octavia-certificates.py').read_text())
            self.assertIn('--project', (out / 'amphora-register.sh').read_text())
            self.assertIn('--tag amphora', (out / 'amphora-register.sh').read_text())
            self.assertIn('enable_octavia=no', commands)
            self.assertIn('octavia-register.yml', commands)
            stages = ['-e enable_octavia=no', '. "$runtime/kolla/admin-openrc.sh"',
                      'bash "$runtime/provider-assets.sh"', '--tags kolla_toolbox',
                      '-p "$runtime/octavia-register.yml"', 'bash "$runtime/amphora-register.sh"',
                      'python "$runtime/octavia-certificates.py"']
            order = [commands.index(stage) for stage in stages]
            self.assertEqual(order, sorted(order))
            for script in ('kolla-commands.sh', 'amphora-build.sh', 'amphora-register.sh', 'provider-assets.sh'):
                check = subprocess.run(['bash', '-n', str(out / script)], capture_output=True, text=True)
                self.assertEqual(check.returncode, 0, check.stderr)
            compile((out / 'octavia-certificates.py').read_text(), 'octavia-certificates.py', 'exec')
            import re
            import sys
            validators = re.findall(r"<<'PY'\n(.*?)\nPY", (out / 'provider-assets.sh').read_text(), re.S)
            self.assertEqual(len(validators), 3)
            valid = subprocess.run([sys.executable, '-c', validators[0], 'vlan', '120', '198.51.100.0/24', '198.51.100.1', '198.51.100.100', '198.51.100.199'], capture_output=True)
            self.assertEqual(valid.returncode, 0, valid.stderr)
            fixture = Path(tmp) / 'network.json'
            network = {'name': 'public', 'project_id': 'INERT_PROJECT', 'router:external': True, 'shared': True,
                       'provider:network_type': 'vlan', 'provider:physical_network': 'physnet1', 'provider:segmentation_id': 120}
            for matched in (True, False):
                network['provider:segmentation_id'] = 120 if matched else 121
                fixture.write_text(json.dumps(network))
                checked = subprocess.run([sys.executable, '-c', validators[1], str(fixture), 'public', 'INERT_PROJECT', 'vlan', 'physnet1', '120'], capture_output=True)
                self.assertEqual(checked.returncode == 0, matched)
            denied = subprocess.run([sys.executable, str(out / 'octavia-certificates.py')], env={**os.environ, 'ALLOW_OCTAVIA_CERTIFICATES': ''}, capture_output=True, text=True)
            self.assertNotEqual(denied.returncode, 0)
            self.assertIn('approval required', denied.stderr)



class VendorContract(unittest.TestCase):
    def test_provider_vlan_has_native_ml2_override_producer(self):
        self.assertTrue((ROOT / 'templates/ml2_conf.ini.j2').is_file(), 'missing native provider VLAN configuration producer')
        text = (ROOT / 'templates/globals.yml.j2').read_text()
        self.assertNotIn('neutron_network_vlan_ranges:', text)
        self.assertIn('config/neutron/ml2_conf.ini', (ROOT / 'render.yml').read_text())
        commands = (ROOT / 'templates/kolla-commands.sh.j2').read_text()
        self.assertIn('kolla-ansible bootstrap-servers -i', commands)
        self.assertIn('utils.get_data_files_path("etc_examples", "kolla", "passwords.yml")', commands)


class CephContract(unittest.TestCase):
    def test_ceph_pipeline_refuses_unreviewed_seed_before_remote_access(self):
        self.assertTrue((ROOT / 'ceph.yml').is_file(), 'missing native Ceph producer')
        ansible = os.environ.get('ANSIBLE_PLAYBOOK', shutil.which('ansible-playbook') or '')
        result = subprocess.run([ansible, '-i', 'localhost,', '-c', 'local', str(ROOT / 'ceph.yml'), '-e', '@' + str(ROOT / 'vars.example.yml')], cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Prepared Ubuntu', result.stdout + result.stderr)
        self.assertNotIn('UNREACHABLE', result.stdout + result.stderr)

    def test_runtime_handoff_writes_private_service_keys_without_stdout_leak(self):
        tasks = ROOT / 'tasks/ceph-handoff.yml'
        self.assertTrue(tasks.is_file(), 'missing independently executable native runtime handoff')
        ansible = os.environ.get('ANSIBLE_PLAYBOOK', shutil.which('ansible-playbook') or '')
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp) / 'runtime'
            runtime.mkdir(mode=0o700)
            fixture_key = 'INERT_UNIT_TEST_KEY_NOT_A_CEPH_SECRET'
            play = [{'hosts': 'localhost', 'gather_facts': False, 'vars': {
                'foundation_runtime': str(runtime),
                'foundation_minimal_conf': {'stdout': '[global]\n\tmon_host = 192.0.2.21\n'},
                'foundation_service_keyrings': {'results': [{'item': {'name': name}, 'stdout': '[client.' + name + ']\nkey = ' + fixture_key} for name in ('glance', 'cinder', 'cinder-backup')]},
                'foundation_ceph_handoffs': [{'client': 'glance', 'target': 'glance'}, {'client': 'cinder', 'target': 'nova'}]},
                'tasks': [{'ansible.builtin.import_tasks': str(tasks)}]}]
            source = Path(tmp) / 'fixture.json'
            source.write_text(json.dumps(play))
            result = subprocess.run([ansible, '-i', 'localhost,', '-c', 'local', str(source)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn(fixture_key, result.stdout + result.stderr)
            key = runtime / 'kolla/config/nova/ceph.client.cinder.keyring'
            self.assertIn(fixture_key, key.read_text())
            self.assertEqual(key.stat().st_mode & 0o777, 0o600)
            self.assertNotIn('\t', (runtime / 'kolla/config/nova/ceph.conf').read_text())
            self.assertEqual(key.parent.stat().st_mode & 0o777, 0o700)

    def test_native_ceph_osds_and_handoff_are_explicit_and_protected(self):
        self.assertTrue((ROOT / 'tasks/ceph-cluster.yml').is_file(), 'missing native Ceph cluster tasks')
        cluster = (ROOT / 'tasks/ceph-cluster.yml').read_text()
        self.assertIn('foundation_allow_osd_prepare', cluster)
        self.assertIn('orch, daemon, add, osd', cluster)
        self.assertNotIn('--all-available-devices', cluster)
        self.assertNotIn('--fsid', cluster)
        self.assertNotIn('zap', cluster)
        self.assertNotIn('cephadm_strict_ssh_qualified', (ROOT / 'ceph.yml').read_text())
        gate = ROOT / 'tasks/ceph-authorization.yml'
        self.assertTrue(gate.is_file(), 'missing honest native-model acceptance gate')
        ansible = os.environ.get('ANSIBLE_PLAYBOOK', shutil.which('ansible-playbook') or '')
        with tempfile.TemporaryDirectory() as tmp:
            play = Path(tmp) / 'gate.json'
            play.write_text(json.dumps([{'hosts': 'localhost', 'gather_facts': False,
                'vars': {'foundation_inputs_reviewed': True, 'foundation_allow_ceph_bootstrap': True},
                'tasks': [{'ansible.builtin.import_tasks': str(gate)}]}]))
            for accepted in ('false', 'true'):
                result = subprocess.run([ansible, '-i', 'localhost,', '-c', 'local', str(play), '-e',
                    'foundation_operator_accepts_cephadm_ssh_trust_model=' + accepted], capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, accepted == 'true', result.stdout + result.stderr)
                self.assertNotIn('UNREACHABLE', result.stdout + result.stderr)
        self.assertNotIn('--ssh-config', cluster)
        self.assertIn('host_key_checking = True', (ROOT / 'ansible.cfg').read_text())
        self.assertIn('lsblk', (ROOT / 'preflight.yml').read_text())
        handoff = (ROOT / 'ceph-clients.yml').read_text() + (ROOT / 'tasks/ceph-handoff.yml').read_text()
        self.assertIn('profile rbd-read-only pool=images', handoff)
        self.assertIn('no_log: true', handoff)
        self.assertIn("mode: '0600'", handoff)
        self.assertNotIn('allow *', handoff)


if __name__ == '__main__':
    unittest.main()
