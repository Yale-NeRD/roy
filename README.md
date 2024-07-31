# Roy: a Python library for distributed shared memory
Roy enables shared memory between multiple processes.
- Core Roy library is written in Rust.

## How to run a simple example
```bash
make example
```
The source code is located at [`src/examples/pi_compute/pi_compute.py`](https://github.com/Yale-NeRD/roy/blob/main/src/examples/pi_compute/pi_compute.py).

## Tests
```bash
make test
```

## Reference
- The locking-based programming model is inspired by [GCP](https://arxiv.org/abs/2301.02576).
