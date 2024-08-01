.PHONY: help build develop test clean

build: build_pyx pydep

test:
	@python -m pytest -v tests/*.py

test_debug: build
	@python -m pytest -v src/tests/roy_set_single.py

pydep:
	@pip install -r src/roy_on_ray/requirements.txt

build_pyx:
	@python3 -m build

install: build
	@pip install dist/*.whl

# clean rust and pycache
clean:
	@rm -rf src/roy_on_ray/build
	@rm -rf dist build
	@cd src/roy_on_ray && rm -rf *.so *.c
	@find . -type d -name __pycache__ -exec rm -r {} \+

# example
example:
	@cd examples/pi_compute && python pi_compute.py
