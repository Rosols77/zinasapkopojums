.PHONY: test test-local test-docker

test: test-local

test-local:
	python3 -m unittest discover -s tests -p 'test_*.py' -v

test-docker:
	docker compose -f docker-compose.test.yml run --rm tests
