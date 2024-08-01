# Roy: a Python library for distributed shared memory

[![Homepage](https://img.shields.io/badge/Homepage-Visit-blue)](https://yale-nerd.github.io/roy/)


Roy enables mutable remote objects on Ray. Please check out our [homepage](https://yale-nerd.github.io/roy/) for more information.

## How to run a simple example
1) Install the Roy library.
```bash
pip install roy-on-ray
```
2) Run the example.
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
