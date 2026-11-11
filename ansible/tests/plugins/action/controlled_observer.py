"""Bounded in-memory state observations; never executes a remote module."""
import base64
import json
import os
from ansible.plugins.action import ActionBase


class ActionModule(ActionBase):
    def run(self, tmp=None, task_vars=None):
        v = task_vars
        action = self._task.args['observed_action']
        args = self._task.args['observed_args']
        host = self._task.delegate_to or v['inventory_hostname']
        state = v['fixture_states'].get(host, {})
        event = {'host': host, 'action': action, 'args': args,
                 'task': self._task.args['observed_name']}
        # Single append write keeps worker records intact without shared state.
        fd = os.open(v['fixture_events'], os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        os.write(fd, (json.dumps(event) + '\n').encode())
        os.close(fd)
        if action in ['setup', 'gather_facts']:
            return {'ansible_facts': {'distribution': 'Ubuntu', 'distribution_version': '24.04'}}
        if action == 'stat':
            return {'stat': {'exists': args['path'] in state}}
        if action == 'slurp':
            if args['src'] not in state:
                return {'failed': True, 'msg': 'Controlled observer: missing file'}
            return {'content': base64.b64encode(state[args['src']].encode()).decode(), 'encoding': 'base64'}
        return {'failed': True, 'msg': 'FIRST_MUTATION_SENTINEL', 'changed': False}
