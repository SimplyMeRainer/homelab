#!/usr/bin/env python3
"""Offline safety checks on native `docker compose config --format json` output."""
import argparse
import ipaddress
import json
import pathlib
import re
import stat


def check_compose(config):
    for name, service in config.get('services', {}).items():
        if service.get('privileged') or service.get('network_mode') == 'host':
            raise ValueError(name + ': privileged or host networking forbidden')
        if 'docker.sock' in json.dumps(service.get('volumes', [])):
            raise ValueError(name + ': Docker socket mount forbidden')
        for port in service.get('ports', []):
            address = port.get('host_ip')
            if not address:
                raise ValueError(name + ': explicit host IP required')
            ip = ipaddress.ip_address(address)
            if ip.is_unspecified or ip.is_multicast:
                raise ValueError(name + ': exposed/invalid host bind')
        if name == 'vault':
            command = service.get('command', [])
            text = ' '.join(command) if isinstance(command, list) else command
            if re.search(r'(^|\s)-{1,2}dev(?:[=\s]|$)', text):
                raise ValueError('Vault dev mode forbidden')
            if 'VAULT_DEV_ROOT_TOKEN_ID' in service.get('environment', {}):
                raise ValueError('Vault development token forbidden')


def check_keys(directory):
    directory = pathlib.Path(directory)
    keys = list(directory.glob('*.key'))
    if not keys:
        raise ValueError('no private keys')
    if stat.S_IMODE(directory.stat().st_mode) != 0o700:
        raise ValueError('TLS directory must be mode 0700')
    for key in keys:
        mode = key.lstat().st_mode
        if not stat.S_ISREG(mode) or stat.S_IMODE(mode) != 0o600:
            raise ValueError('private key must be a regular, mode 0600 file: ' + key.name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('compose_json', type=pathlib.Path)
    parser.add_argument('--keys', type=pathlib.Path)
    args = parser.parse_args()
    check_compose(json.loads(args.compose_json.read_text()))
    if args.keys:
        check_keys(args.keys)
    print('management configuration safety checks passed (not runtime qualification)')


if __name__ == '__main__':
    main()
