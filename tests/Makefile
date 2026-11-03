PYTHON := .venv/bin/python

.PHONY: install
install:
	uv sync

.PHONY: test-unit
test-unit:
	$(PYTHON) -m vedro run unit/scenarios

.PHONY: test-e2e
test-e2e:
	$(PYTHON) -m vedro run e2e/scenarios

.PHONY: test
test: test-unit test-e2e
