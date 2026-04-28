# revizēts makefile ar opsistēmas atpazīšanu
ifeq ($(shell python3 --version 2>/dev/null),)
    PYTHON := python
else
    PYTHON := python3
endif

.PHONY: test test-local test-script test-observability test-all test-docker

test: test-local

test-local:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

test-script:
	$(PYTHON) run_tests.py

test-observability:
	$(PYTHON) run_observability_demo.py

test-all: test-local test-script test-observability

test-docker:
	docker compose -f docker-compose.test.yml up --build --abort-on-container-exit