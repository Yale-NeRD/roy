# Roy: a Python library for distributed shared memory

[![Homepage](https://img.shields.io/badge/Homepage-Visit-blue)](https://yale-nerd.github.io/roy/)


Roy enables shared memory between multiple processes.
- Core Roy library is written in Rust.

## How to run a simple example
First, install the Roy library (recommended to use a virtual environment). This will install the Roy library in _editable_ mode (`pip install` with `-e` flag).
```bash
make install
```
Then run the example.
```bash
make example
```
The source code is located at [`examples/pi_compute/pi_compute.py`](https://github.com/Yale-NeRD/roy/blob/main/examples/pi_compute/pi_compute.py).

## Tests
```bash
make test
```

## Reference
- The locking-based programming model is inspired by [GCP](https://arxiv.org/abs/2301.02576).
