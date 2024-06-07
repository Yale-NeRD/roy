use pyo3::prelude::*;
use pyo3::types::{PySet, PyAny};
use pyo3::exceptions::PyIndexError;

#[pyclass]
pub struct Royset {
    chunk_ref_list: Vec<PyObject>,
    chunk_size: usize,
    len: usize,
    num_chunks: usize,
    chunk_list: Vec<Vec<PyObject>>,
}

#[pymethods]
impl Royset {
    #[new]
    pub fn new(py: Python, ref_list: &PySet, chunk_size: usize, len: usize, idx: Option<usize>) -> PyResult<Self> {
        if ref_list.len() == 0 {
            return Err(PyErr::new::<pyo3::exceptions::PyAssertionError, _>("Value cannot be None"));
        }
        if chunk_size <= 0 {
            return Err(PyErr::new::<pyo3::exceptions::PyAssertionError, _>("Chunk size must be greater than 0"));
        }

        let ray = py.import_bound("ray")?;
        if !ray.getattr("is_initialized")?.call0()?.extract()? {
            return Err(PyErr::new::<pyo3::exceptions::PyAssertionError, _>("Ray must be initialized"));
        }

        // transform ref_list into chunk_ref_list
        let chunk_ref_list: Vec<PyObject> = ref_list.extract()?;
        let num_chunks = chunk_ref_list.len();
        let mut chunk_list = vec![vec![]; num_chunks];
    
        // preload
        if let Some(chunk_idx) = idx {
            if chunk_list[chunk_idx].len() == 0 {
                let chunk = ray.call_method1("get", (chunk_ref_list[chunk_idx].clone_ref(py),))?;
                let chunk: Vec<PyObject> = chunk.extract()?;
                chunk_list[chunk_idx] = chunk;
            }
        }
        println!("Total chunks: {}", num_chunks);

        Ok(Royset {
            chunk_ref_list,
            chunk_size,
            len,
            num_chunks,
            chunk_list,
        })
    }

    pub fn __getitem__(&mut self, py: Python, idx: usize) -> PyResult<PyObject> {
        if idx >= self.len {
            return Err(PyIndexError::new_err("Index out of range"));
        }

        let chunk_idx = idx / self.chunk_size;
        if self.chunk_list[chunk_idx].len() == 0 {
            let ray = py.import_bound("ray")?;
            let chunk = ray.call_method1("get", (self.chunk_ref_list[chunk_idx].clone_ref(py),))?;
            let chunk: Vec<PyObject> = chunk.extract()?;
            self.chunk_list[chunk_idx] = chunk;
        }
        Ok(self.chunk_list[chunk_idx][idx % self.chunk_size].clone())
    }
}
