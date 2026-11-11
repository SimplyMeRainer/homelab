"""Offline only: run actual coordinator/asserts, intercept EVERY I/O action.

Unknown actions fail closed at the first-mutation sentinel; no guest module runs.
"""
from ansible.plugins.strategy.linear import StrategyModule as Linear


class StrategyModule(Linear):
    def _queue_task(self, host, task, task_vars, play_context):
        safe = {'assert', 'set_fact', 'debug', 'include_tasks', 'include_role'}
        action = task.action.rsplit('.', 1)[-1]
        if action not in safe:
            task = task.copy()
            task.args = {'observed_action': action, 'observed_args': task.args,
                         'observed_name': task.get_name()}
            task.action = 'controlled_observer'
        return super()._queue_task(host, task, task_vars, play_context)
