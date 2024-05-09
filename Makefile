.PHONY: help build develop test clean

test: build pydep
	@cd src/pyroy && python -m pytest

pydep:
	@pip install -r src/pyroy/requirements.txt

build:
	@cd src/roy_shmem && maturin develop

# clean rust and pycache
clean:
	@cd src/roy_shmem && cargo clean
	@find . -type d -name __pycache__ -exec rm -r {} \+