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
	docker build -t tailoredscoop .

docker-push:
	docker tag tailoredscoop:latest chansoosong/tailoredscoop:1.0.0 \
	&& docker push chansoosong/tailoredscoop:1.0.0
