"""Offline native Ansible checks. Never connects to a guest or Kubernetes API."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ANSIBLE = os.environ.get('ANSIBLE_PLAYBOOK') or shutil.which('ansible-playbook') or '/opt/homebrew/bin/ansible-playbook'


def run_play(play, inventory, *extra):
    env = dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible.cfg'), ANSIBLE_NOCOLOR='1')
    return subprocess.run([ANSIBLE, '-i', str(inventory), str(play), *extra],
                          cwd=ROOT, env=env, text=True, capture_output=True)


class WorkflowTests(unittest.TestCase):
    def admission_run(self, entrypoint, lab='lab-01', state='fresh', unsafe=None):
        """Actual supported entrypoint; all I/O is bounded/controlled, not SSH."""
        import json
        import yaml
        hosts = ['cp1', 'cp2', 'cp3', 'worker1', 'worker2']
        common = dict(cluster_name=lab, kube_context=f'{lab}-admin@{lab}',
                      api_endpoint='api.lab.example:6443', api_vip='203.0.113.10',
                      pod_cidr='10.244.0.0/16', service_cidr='10.96.0.0/16',
                      kube_vip_interface='ens3', lab_inputs_confirmed=True,
                      ansible_connection='local', ansible_become=False)
        nodes = {h: {'node_ip': f'203.0.113.{11+i}'} for i, h in enumerate(hosts)}
        states = {h: {} for h in hosts}
        releases = yaml.safe_load((ROOT / 'vars/releases.yml').read_text())
        for h in hosts:
            identity = {k: common[k] for k in ['cluster_name', 'api_endpoint', 'api_vip',
                        'pod_cidr', 'service_cidr', 'kube_vip_interface']}
            identity.update(node_ip=nodes[h]['node_ip'], version=releases['kubernetes_version'], topology=hosts)
            if state != 'fresh':
                states[h]['/etc/kubernetes/lab-kit-identity.json'] = json.dumps(identity)
            if state == 'resume':
                ca = {'certificate-authority-data': 'INERT-FIXTURE-CA',
                      'server': 'https://' + (nodes[h]['node_ip'] + ':6443' if h.startswith('cp') else common['api_endpoint'])}
                states[h]['/etc/kubernetes/kubelet.conf'] = yaml.safe_dump({'clusters': [{'cluster': ca}]})
                if h == 'cp1':
                    states[h]['/etc/kubernetes/admin.conf'] = yaml.safe_dump({'clusters': [{'cluster': ca}]})
                    states[h]['/etc/kubernetes/lab-kit-init-complete'] = 'complete'
        if unsafe:
            host, defect = unsafe
            if defect == 'marker':
                identity = json.loads(states[host]['/etc/kubernetes/lab-kit-identity.json'])
                identity['version'] = 'v0.0.0'
                states[host]['/etc/kubernetes/lab-kit-identity.json'] = json.dumps(identity)
            elif defect == 'unmarked':
                states[host].pop('/etc/kubernetes/lab-kit-identity.json', None)
                states[host]['/etc/kubernetes/pki/ca.crt'] = 'inert'
            elif defect == 'partial':
                states[host].pop('/etc/kubernetes/kubelet.conf', None)
                states[host].pop('/etc/kubernetes/lab-kit-init-complete', None)
                states[host]['/etc/kubernetes/pki/ca.crt'] = 'inert'
            elif defect == 'no-admin':
                states['cp1'].pop('/etc/kubernetes/admin.conf', None)
            elif defect in ['ca', 'endpoint']:
                conf = yaml.safe_load(states[host]['/etc/kubernetes/kubelet.conf'])
                conf['clusters'][0]['cluster']['certificate-authority-data' if defect == 'ca' else 'server'] = 'WRONG'
                states[host]['/etc/kubernetes/kubelet.conf'] = yaml.safe_dump(conf)
        with tempfile.TemporaryDirectory() as d:
            inventory, extra, events = [Path(d) / n for n in ['inventory.yml', 'vars.yml', 'events.jsonl']]
            inventory.write_text(yaml.safe_dump({'all': {'vars': common, 'children': {
                'control_plane': {'hosts': {h: nodes[h] for h in hosts[:3]}},
                'worker': {'hosts': {h: nodes[h] for h in hosts[3:]}}}}}, sort_keys=False))
            extra.write_text(yaml.safe_dump({'fixture_states': states, 'fixture_events': str(events)}))
            env = dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible.cfg'), ANSIBLE_NOCOLOR='1',
                       ANSIBLE_STRATEGY='controlled',
                       ANSIBLE_STRATEGY_PLUGINS=str(ROOT / 'tests/plugins/strategy'),
                       ANSIBLE_ACTION_PLUGINS=str(ROOT / 'tests/plugins/action'))
            p = subprocess.run([ANSIBLE, '-i', str(inventory), str(ROOT / entrypoint), '-e', '@' + str(extra)],
                               cwd=ROOT, env=env, text=True, capture_output=True, timeout=45)
            records = [json.loads(line) for line in events.read_text().splitlines()] if events.exists() else []
            mutations = [e for e in records if e['action'] not in ['setup', 'gather_facts', 'stat', 'slurp']]
            if os.environ.get('ANSIBLE_TEST_EVIDENCE_DIR'):
                evidence = Path(os.environ['ANSIBLE_TEST_EVIDENCE_DIR'])
                evidence.mkdir(parents=True, exist_ok=True)
                case = '-'.join([entrypoint, lab, state, *(unsafe or ['positive'])])
                (evidence / (case + '.log')).write_text(p.stdout + p.stderr)
                (evidence / (case + '.json')).write_text(json.dumps(records, indent=2))
            self.assertNotEqual(p.returncode, 0, 'Fixture must stop at refusal or first-mutation sentinel')
            self.assertNotIn('UNREACHABLE', p.stdout + p.stderr)
            if unsafe:
                self.assertEqual(mutations, [], p.stdout + p.stderr)
                self.assertNotIn('FIRST_MUTATION_SENTINEL', p.stdout + p.stderr)
                expected_guard = {'marker': 'Refuse mismatched cluster or changed immutable inputs',
                                  'unmarked': 'Refuse adoption of an unmarked cluster',
                                  'partial': 'Refuse ambiguous partial init' if unsafe[0] == 'cp1' else 'Refuse partial join',
                                  'no-admin': 'Require authoritative identity for an existing kubelet',
                                  'ca': 'Refuse an existing node from a mismatched cluster',
                                  'endpoint': 'Refuse an existing node from a mismatched cluster'}[unsafe[1]]
                self.assertIn(expected_guard, p.stdout + p.stderr)
                self.assertNotIn('Syntax Error', p.stdout + p.stderr)
                self.assertNotIn('Error while evaluating conditional', p.stdout + p.stderr)
            else:
                self.assertTrue(mutations, p.stdout + p.stderr)
                self.assertIn('FIRST_MUTATION_SENTINEL', p.stdout + p.stderr)
                before = records[:records.index(mutations[0])]
                admitted = {e['host'] for e in before if e['action'] == 'stat' and e['args']['path'] == '/etc/kubernetes/lab-kit-identity.json'}
                self.assertEqual(admitted, set(hosts), p.stdout + p.stderr)
                if state == 'resume':
                    checked = {e['host'] for e in before if e['action'] == 'slurp' and e['args']['src'] == '/etc/kubernetes/kubelet.conf'}
                    self.assertEqual(checked, set(hosts), p.stdout + p.stderr)
                else:
                    self.assertFalse(any(e['action'] == 'slurp' and e['args']['src'] == '/etc/kubernetes/admin.conf' for e in before))

    def test_baseline_all_target_admission_before_first_mutation(self):
        for state, unsafe in [('resume', ('worker2', 'marker')), ('fresh', ('worker2', 'unmarked')),
                              ('resume', ('worker2', 'ca')), ('resume', ('worker2', 'partial'))]:
            with self.subTest(state=state, unsafe=unsafe):
                self.admission_run('baseline.yml', state=state, unsafe=unsafe)
        for lab, state in [('lab-01', 'fresh'), ('lab-02', 'fresh'), ('lab-01', 'resume')]:
            with self.subTest(lab=lab, state=state):
                self.admission_run('baseline.yml', lab=lab, state=state)

    def test_site_all_node_state_refusals_before_first_mutation(self):
        for host, defect in [('worker2', 'ca'), ('cp3', 'endpoint'),
                             ('worker2', 'partial'), ('cp1', 'partial'),
                             ('cp1', 'ca'), ('worker2', 'no-admin')]:
            with self.subTest(host=host, defect=defect):
                self.admission_run('site.yml', state='resume', unsafe=(host, defect))
        for state in ['fresh', 'resume']:
            with self.subTest(state=state):
                self.admission_run('site.yml', state=state)

    def test_identity_mismatch_and_native_readiness_command(self):
        with tempfile.TemporaryDirectory() as d:
            fake = Path(d) / 'kubectl-fixture'
            fake.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "' + d + '/argv"\nprintf ok\n')
            fake.chmod(0o700)
            p = run_play(ROOT / 'tests/fixtures/runtime.yml', 'localhost,',
                         '-e', 'fixture_kubectl=' + str(fake))
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            args = (Path(d) / 'argv').read_text().splitlines()
            self.assertEqual(args, ['--kubeconfig=/etc/kubernetes/admin.conf',
                                    '--context=kubernetes-admin@lab-01', '--server=https://203.0.113.11:6443', 'get', '--raw=/readyz'])

    def test_bootstrap_templates_and_runtime_secret_contract(self):
        import yaml
        p = run_play(ROOT / 'site.yml', ROOT / 'inventory.example.yml', '--syntax-check')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        with tempfile.TemporaryDirectory() as d:
            p = run_play(ROOT / 'tests/fixtures/render.yml', 'localhost,', '-e', 'fixture_dir=' + d)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            init = list(yaml.safe_load_all((Path(d) / 'kubeadm.yml').read_text()))
            self.assertEqual(init[0]['nodeRegistration']['kubeletExtraArgs'], [{'name': 'node-ip', 'value': '203.0.113.11'}])
            self.assertEqual(init[1]['controlPlaneEndpoint'], 'api.lab.example:6443')
            self.assertEqual(init[1]['clusterName'], 'lab-01')
            for name in ['bootstrap', 'steady']:
                pod = yaml.safe_load((Path(d) / (name + '.yml')).read_text())
                self.assertIn('@sha256:', pod['spec']['containers'][0]['image'])
                self.assertIn('annotations', pod['metadata'], 'Credential transition must restart the static pod')
                self.assertEqual(pod['metadata']['annotations']['lab-kit.example/credentials'], 'super-admin.conf' if name == 'bootstrap' else 'admin.conf')
                self.assertEqual(pod['spec']['volumes'][0]['hostPath']['path'], '/etc/kubernetes/kube-vip.conf')
            self.assertTrue((Path(d) / 'admin.kubeconfig').exists(), 'Private context-bound output is missing')
            exported = yaml.safe_load((Path(d) / 'admin.kubeconfig').read_text())
            self.assertEqual(exported['current-context'], 'lab-01-admin@lab-01')
            self.assertEqual(len(exported['contexts']), 1)
            self.assertEqual(exported['clusters'][0]['cluster']['server'], 'https://api.lab.example:6443')
            self.assertEqual((Path(d) / 'admin.kubeconfig').stat().st_mode & 0o777, 0o600)
            local_vip = yaml.safe_load((Path(d) / 'vip.kubeconfig').read_text())
            self.assertEqual(local_vip['clusters'][0]['cluster']['server'], 'https://203.0.113.11:6443')
            join = yaml.safe_load((Path(d) / 'join.yml').read_text())
            self.assertIn('caCertHashes', join['discovery']['bootstrapToken'])
            self.assertNotIn('unsafeSkipCAVerification', join['discovery']['bootstrapToken'])
        cilium_tasks = yaml.safe_load((ROOT / 'roles/cluster/tasks/cilium.yml').read_text())
        render_task = next(t for t in cilium_tasks if 'ansible.builtin.command' in t and 'template' in t['ansible.builtin.command'].get('argv', []))
        self.assertIn('--set=hubble.enabled=false', render_task['ansible.builtin.command']['argv'], 'Optional Hubble Helm TLS generation must not rotate secrets on rerun')
        secret_tasks = yaml.safe_load((ROOT / 'roles/cluster/tasks/join.yml').read_text())
        block = next(t for t in secret_tasks if 'always' in t)
        self.assertTrue(block['no_log'])
        self.assertTrue(block['always'])

    def test_baseline_syntax_and_swap_persistence_fixture(self):
        p = run_play(ROOT / 'baseline.yml', ROOT / 'inventory.example.yml', '--syntax-check')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        with tempfile.TemporaryDirectory() as d:
            fstab = Path(d) / 'fstab'
            fstab.write_text('/dev/vda1 / ext4 defaults 0 1\n/swap.img\tnone\tswap\tsw\t0\t0\n# /old none swap sw 0 0\n')
            p = run_play(ROOT / 'tests/fixtures/swap.yml', 'localhost,',
                         '-e', 'fixture_fstab=' + str(fstab))
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertIn('# disabled by homelab kit: /swap.img', fstab.read_text())
            self.assertIn('/dev/vda1 / ext4 defaults 0 1', fstab.read_text())

    def test_lab02_refused_before_any_guest_connection(self):
        with tempfile.TemporaryDirectory() as d:
            inventory = Path(d) / 'inventory.yml'
            inventory.write_text('all:\n  vars:\n    cluster_name: lab-02\n  children:\n    control_plane:\n      hosts:\n        cp1:\n          ansible_host: 192.0.2.11\n    worker:\n      hosts:\n        worker1:\n          ansible_host: 192.0.2.21\n')
            p = run_play(ROOT / 'site.yml', inventory, '--check')
            self.assertNotEqual(p.returncode, 0)
            self.assertIn('site.yml supports ONLY lab-01', p.stdout + p.stderr)
            self.assertNotIn('UNREACHABLE', p.stdout + p.stderr)


if __name__ == '__main__':
    unittest.main()
