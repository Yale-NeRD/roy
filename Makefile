.PHONY: help build develop test clean

build: build_pyx pydep

test: build
	@python -m pytest -v src/tests/*.py

test_debug: build
	@python -m pytest -v src/tests/roy_set_single.py

test_py: build_py pydep
	@cd src/pyroy && python -m pytest -v

pydep:
	@pip install -r src/roytypes/requirements.txt

build_pyx:
	@cd src/roytypes && make

# clean rust and pycache
clean:
	@cd src/roytypes && make clean
	@find . -type d -name __pycache__ -exec rm -r {} \+

# example
example: build
	@cd src/examples && python pi_compute.py
