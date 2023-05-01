.PHONY: tests_all test-file book serve

tests_all:
	poetry run pytest -v -rP

test-file:
	poetry run pytest -v -rP $(file)

book:
	poetry run jb build book

serve:
	python -m http.server -d book/_build/html $(port)