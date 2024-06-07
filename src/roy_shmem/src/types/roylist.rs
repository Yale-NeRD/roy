use pyo3::prelude::*;
use pyo3::types::{PyList, PyAny};
use pyo3::exceptions::PyIndexError;

#[pyclass]
pub struct Roylist {
    chunk_ref_list: Vec<PyObject>,
    chunk_size: usize,
    len: usize,
    num_chunks: usize,
    chunk_list: Vec<Vec<PyObject>>,
    access_latency: f64,
    access_count: usize,
}

#[pymethods]
impl Roylist {
    #[new]
    pub fn new(py: Python, ref_list: &PyList, chunk_size: usize, len: usize, idx: Option<usize>) -> PyResult<Self> {
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

        Ok(Roylist {
            chunk_ref_list,
            chunk_size,
            len,
            num_chunks,
            chunk_list,
            access_latency: 0.0,
            access_count: 0,
        })
    }

    pub fn __getitem__(&mut self, py: Python, idx: usize) -> PyResult<PyObject> {
        if idx >= self.len {
            return Err(PyIndexError::new_err("Index out of range"));
        }

        // let mut fetch: bool = false;
        // let start = std::time::Instant::now();
        let chunk_idx = idx / self.chunk_size;
        if self.chunk_list[chunk_idx].len() == 0 {
            let ray = py.import_bound("ray")?;
            let chunk_ref = self.chunk_ref_list[chunk_idx].clone_ref(py);
            let chunk: Vec<PyObject> = ray.call_method1("get", (chunk_ref,))?.extract()?;
            self.chunk_list[chunk_idx] = chunk;
            // fetch = true;
        }
        // let result = self.chunk_list[chunk_idx][idx % self.chunk_size].clone_ref(py);
        // if !fetch {
        //     self.access_latency += start.elapsed().as_secs_f64();
        //     self.access_count += 1;
        // }
        // NOTE) result was 50 ns
        // Ok(result)

        //
        Ok(self.chunk_list[chunk_idx][idx % self.chunk_size].clone_ref(py))
    }

    pub fn get_access_latency(&self) -> f64 {
        if self.access_count == 0 {
            return 0.0;
        }
        self.access_latency / self.access_count as f64
    }
}

#[pyfunction]
pub fn optimized_getitem(
    py: Python,
    idx: usize,
    chunk_size: usize,
    chunk_ref_list: &PyList,
    chunk_list: &PyList,
) -> PyResult<PyObject> {
    let chunk_ref_list: Vec<PyObject> = chunk_ref_list.extract()?;

    if idx >= chunk_ref_list.len() * chunk_size {
        return Err(PyIndexError::new_err("Index out of range"));
    }

    let chunk_idx = idx / chunk_size;

    // println!("Before: Chunk idx: {:?}", chunk_list.get_item(chunk_idx)?.len());
    if chunk_list.get_item(chunk_idx)?.is_none() {
        let ray = py.import_bound("ray")?;
        let chunk = ray.call_method1("get", (chunk_ref_list[chunk_idx].clone_ref(py),))?;
        chunk_list.set_item(chunk_idx, chunk)?;
    }
    // println!("After: Chunk idx: {:?}", chunk_list.get_item(chunk_idx)?.len());

    let chunk: &PyAny = chunk_list.get_item(chunk_idx)?;
    let chunk_list: &PyList = chunk.extract()?;
    let item = chunk_list.get_item(idx % chunk_size)?;
    Ok(item.to_object(py))
}
