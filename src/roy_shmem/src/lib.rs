use pyo3::prelude::*;
use pyo3::Bound;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::net::IpAddr;

#[pyclass]
struct SharedMemory {
    data: Arc<Mutex<HashMap<String, String>>>,
    server_ip_addr: Option<IpAddr>
}

#[pymethods]
impl SharedMemory {
    #[new]
    fn new() -> Self {
        SharedMemory {
            data: Arc::new(Mutex::new(HashMap::new())),
            server_ip_addr: None
        }
    }

    fn init(&mut self, server_ip_addr: IpAddr) -> PyResult<()> {
        self.server_ip_addr = Some(server_ip_addr);
        Ok(())
    }

    fn read(&self, key: String) -> PyResult<Option<String>> {
        let data = self.data.lock().unwrap();
        Ok(data.get(&key).cloned())
    }

    fn write(&self, key: String, value: String) -> PyResult<()> {
        let mut data = self.data.lock().unwrap();
        data.insert(key, value);
        Ok(())
    }
}

#[pymodule]
#[allow(dead_code)]
fn roy_shmem(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<SharedMemory>()?;
    Ok(())
}