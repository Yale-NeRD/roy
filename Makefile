.PHONY: help build develop test clean

build: build_py pydep

test: build_py pydep
	@cd src/pyroy && python -m pytest -v

pydep:
	@pip install -r src/pyroy/requirements.txt
	# @pip install -r src/roy_ctrl/requirements.txt

build_all: build_py build_ctrl

# install_ctrl: build_ctrl
# 	@cd src/roy_ctrl && python setup.py sdist bdist_wheel && pip install .

build_py:
	@cd src/roy_shmem && maturin develop --release

build_ctrl:
	@echo "Skip roy_ctrl"
	@cd src/roy_ctrl && maturin develop

# clean rust and pycache
clean:
	@cd src/roy_shmem && cargo clean
	@find . -type d -name __pycache__ -exec rm -r {} \+
	@pip uninstall roy_ctrl

# example
example: build_py pydep
	@cd src/examples && python pi_compute.py
