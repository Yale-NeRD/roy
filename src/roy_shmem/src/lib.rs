mod shared_memory;
mod shared_memory_server;
mod shared_memory_client;

use pyo3::prelude::*;
use pyo3::Bound;
use pyo3::exceptions::PyValueError;
use serde::de::value;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use shared_memory_server::SharedMemoryServer;
use shared_memory_client::SharedMemoryClient;

#[pyclass]
struct SharedMemory {
    data: Arc<Mutex<HashMap<String, String>>>,
    server_instance: Option<SharedMemoryServer>,
    server_connection: Option<SharedMemoryClient>,
}

#[pymethods]
impl SharedMemory {
    #[new]
    fn new() -> Self {
        SharedMemory {
            data: Arc::new(Mutex::new(HashMap::new())),
            server_connection: None,
            server_instance: None,
        }
    }

    fn start_server(&mut self, server_addr: String) -> PyResult<()> {
        let server = SharedMemoryServer::new(server_addr);
        self.server_instance = Some(server);
        let err = self.server_instance.as_mut().unwrap().start();
        if err.is_err() {
            return Err(PyValueError::new_err(err.unwrap_err().to_string()));
        }
        Ok(())
    }

    fn stop_server(&mut self) -> PyResult<()> {
        // if self.server_instance.is_none() {
        //     return Err(PyValueError::new_err("Server not initialized"));
        // }
        // let server = self.server_instance.as_mut().unwrap();
        // server.terminate_server();
        if self.server_connection.is_none() {
            return Err(PyValueError::new_err("Server connection not initialized"));
        }
        let socket: &SharedMemoryClient = self.server_connection.as_ref().unwrap();
        socket.send_terminate_message()?;
        Ok(())
    }

    fn connect_server(&mut self, server_addr: String) -> PyResult<()> {
        let server_conn = SharedMemoryClient::new(server_addr);
        self.server_connection = Some(server_conn);
        let err = self.server_connection.as_mut().unwrap().connect();
        if err.is_err() {
            return Err(PyValueError::new_err(err.unwrap_err().to_string()));
        }
        Ok(())
    }

    fn read(&self, key: String) -> PyResult<Option<String>> {
        println!("Reading from key: {}", key);
        let mut data = self.data.lock().unwrap();
        // TODO: check the cache state if it is safe to use this value
        // if data.contains_key(&key) {
        //     return Ok(data.get(&key).cloned());
        // }
        if self.server_connection.is_none() {
            return Err(PyValueError::new_err("Server connection not initialized"));
        }

        let socket: &SharedMemoryClient = self.server_connection.as_ref().unwrap();
        // use the server connection to request the value of the key
        let value = socket.read_data(&key);
        if value.is_err() {
            return Ok(None);
        }
        let value = value.unwrap();
        data.insert(key.clone(), value.clone());
        Ok(Some(value))
    }

    fn write(&self, key: String, value: String) -> PyResult<()> {
        println!("Writing to key: {}, value: {}", key, value);
        let mut data = self.data.lock().unwrap();
        if self.server_connection.is_none() {
            return Err(PyValueError::new_err("Server connection not initialized"));
        }
        let socket: &SharedMemoryClient = self.server_connection.as_ref().unwrap();
        socket.write_data(&key, &value)?;
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
