.PHONY: tests_all test-file book serve docker-build

tests_all:
	poetry run pytest -v -rP tests/*

test-file:
	poetry run pytest -v -rP $(file)

book:
	poetry run jb build book

serve:
	python -m http.server -d book/_build/html $(port)

docker-build:
	docker build -f Dockerfile -t tailoredscoop .

docker-test:
	docker build -f Dockerfile.test -t tailoredscoop_testing . \
	&& docker tag tailoredscoop_testing:latest chansoosong/tailoredscoop_testing:1.0.0 \
	&& docker push chansoosong/tailoredscoop_testing:1.0.0

docker-push:
	docker build -t tailoredscoop . \
	&& docker tag tailoredscoop:latest chansoosong/tailoredscoop:1.0.0 \
	&& docker push chansoosong/tailoredscoop:1.0.0

docker-today:
	docker build -f Dockerfile.today -t tailoredscoop_today . \
	&& docker tag tailoredscoop_today:latest chansoosong/tailoredscoop_today:1.0.0 \
	&& docker push chansoosong/tailoredscoop_today:1.0.0

fake-server:
	cd tailoredscoop \
	&& uvicorn fakeserver:app --host 0.0.0.0 --port 8080