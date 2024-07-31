.PHONY: help build develop test clean

build: build_pyx pydep

build_pypi: build
	@python3 -m build

test: build
	@python -m pytest -v tests/*.py

test_debug: build
	@python -m pytest -v src/tests/roy_set_single.py

test_py: build_py pydep
	@cd src/pyroy && python -m pytest -v

pydep:
	@pip install -r src/roy_on_ray/requirements.txt

build_pyx:
	@cd src/roy_on_ray && make

install: build
	@pip install -e .

# clean rust and pycache
clean:
	@cd src/roy_on_ray && make clean
	@find . -type d -name __pycache__ -exec rm -r {} \+

# example
example: build
	@cd examples/pi_compute && python pi_compute.py
