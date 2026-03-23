.PHONY: test test-local test-script test-observability test-all test-docker

test: test-local

test-local:
	python3 -m unittest discover -s tests -p 'test_*.py' -v

test-script:
	python3 run_tests.py

test-observability:
	python3 run_observability_demo.py

test-all: test-local test-script test-observability

test-docker:
	docker compose -f docker-compose.test.yml run --rm tests
