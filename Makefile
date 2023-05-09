.PHONY: tests_all test-file book serve docker-build

tests_all:
	poetry run pytest -v -rP

test-file:
	poetry run pytest -v -rP $(file)

book:
	poetry run jb build book

serve:
	python -m http.server -d book/_build/html $(port)

docker-build:
	docker build -f Dockerfile -t tailoredscoop .

docker-build-test:
	docker build -f Dockerfile.debug -t tailoredscoop_testing .

docker-push:
	docker build -t tailoredscoop . \
	&& docker tag tailoredscoop:latest chansoosong/tailoredscoop:1.0.0 \
	&& docker push chansoosong/tailoredscoop:1.0.0

fake-server:
	cd tailoredscoop \
	&& uvicorn fakeserver:app --host 0.0.0.0 --port 8080