.DEFAULT_GOAL := help
.PHONY: help test validate

help:
	@printf '%s\n' 'Homelab development kit' '  make test      Run offline component tests' '  make validate  Run tests and native configuration validation' '' 'No deployment runs from Make or CI. Follow the build guide for operator-run changes.'

test:
	@bash scripts/validate.sh --tests-only

validate:
	@bash scripts/validate.sh
