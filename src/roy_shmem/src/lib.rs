mod shared_memory;
mod shared_memory_server;
mod shared_memory_client;
mod types;

use pyo3::prelude::*;
use pyo3::Bound;
use pyo3::exceptions::PyValueError;
// use serde::de::value;
use types::Roylist;
use types::optimized_getitem;
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
        if self.server_connection.is_some() {
            println!("Server connection already initialized");            
            return Ok(());
        }
        let server_conn = SharedMemoryClient::new(server_addr);
        self.server_connection = Some(server_conn);
        let err = self.server_connection.as_mut().unwrap().connect();
        if err.is_err() {
            return Err(PyValueError::new_err(err.unwrap_err().to_string()));
        }
        Ok(())
    }

    fn get_next_availble_handle(&self, handle: String) -> PyResult<String> {
        if self.server_connection.is_none() {
            return Err(PyValueError::new_err("Server connection not initialized"));
        }
        let socket: &SharedMemoryClient = self.server_connection.as_ref().unwrap();
        let handle = socket.get_next_availble_handle(&handle)?;
        Ok(handle)
    }

    // def set_remote_handle(handle: str, instance):
    //     SharedMemorySingleton().set_handle_object(handle, pickle.dumps(instance))
    fn set_handle_object(&self, handle: String, instance: Vec<u8>) -> PyResult<()> {
        if self.server_connection.is_none() {
            return Err(PyValueError::new_err("Server connection not initialized"));
        }

        println!("Setting handle: {}, Length: {}", handle, instance.len());
        let socket: &SharedMemoryClient = self.server_connection.as_ref().unwrap();
        let res = socket.write_pickle(&handle, &instance);
        if res.is_err() {
            return Err(PyValueError::new_err(res.unwrap_err().to_string()));
        }
        Ok(())
    }

    fn set_handle_object_unlock(&self, handle: String, instance: Vec<u8>, lock: String) -> PyResult<()> {
        if self.server_connection.is_none() {
            return Err(PyValueError::new_err("Server connection not initialized"));
        }

        println!("Setting handle: {}, Length: {}, Lock: {}", handle, instance.len(), lock);
        let socket: &SharedMemoryClient = self.server_connection.as_ref().unwrap();
        let res = socket.write_pickle_unlock(&handle, &instance, &lock);
        if res.is_err() {
            return Err(PyValueError::new_err(res.unwrap_err().to_string()));
        }
        Ok(())
    }

    fn get_handle_object(&self, handle: String) -> PyResult<Option<Vec<u8>>> {
        if self.server_connection.is_none() {
            return Err(PyValueError::new_err("Server connection not initialized"));
        }

        let socket: &SharedMemoryClient = self.server_connection.as_ref().unwrap();
        let res = socket.read_pickle(&handle);
        match res {
            Ok(data) => Ok(Some(data)),
            Err(_) => Ok(None),
        }
    }

    fn get_handle_object_lock(&self, handle: String, lock: String) -> PyResult<Option<Vec<u8>>> {
        if self.server_connection.is_none() {
            return Err(PyValueError::new_err("Server connection not initialized"));
        }
        println!("Getting handle: {}, Lock: {}", handle, lock);

        let socket: &SharedMemoryClient = self.server_connection.as_ref().unwrap();
        let res = socket.read_pickle_lock(&handle, &lock);
        match res {
            Ok(data) => Ok(Some(data)),
            Err(_) => Ok(None),
        }
    }

    // fn read(&self, key: String) -> PyResult<Option<String>> {
    //     println!("Reading from key: {}", key);
    //     let mut data = self.data.lock().unwrap();
    //     // TODO: check the cache state if it is safe to use this value
    //     // if data.contains_key(&key) {
    //     //     return Ok(data.get(&key).cloned());
    //     // }
    //     if self.server_connection.is_none() {
    //         return Err(PyValueError::new_err("Server connection not initialized"));
    //     }

    //     let socket: &SharedMemoryClient = self.server_connection.as_ref().unwrap();
    //     // use the server connection to request the value of the key
    //     let value = socket.read_data(&key);
    //     if value.is_err() {
    //         return Ok(None);
    //     }
    //     let value = value.unwrap();
    //     data.insert(key.clone(), value.clone());
    //     Ok(Some(value))
    // }

    // fn write(&self, key: String, value: String) -> PyResult<()> {
    //     println!("Writing to key: {}, value: {}", key, value);
    //     let mut data = self.data.lock().unwrap();
    //     if self.server_connection.is_none() {
    //         return Err(PyValueError::new_err("Server connection not initialized"));
    //     }
    //     let socket: &SharedMemoryClient = self.server_connection.as_ref().unwrap();
    //     socket.write_data(&key, &value)?;
    //     data.insert(key, value);
    //     Ok(())
    // }
}

#[pyfunction]
fn call_ray_get_ftn(py: Python, ray: &PyAny, remote_function: &PyAny) -> PyResult<()> {
    // Call the remote function with an argument
    let object_ref = remote_function.call1((10,))?;

    // Get the result using `ray.get`
    let result = ray.call_method1("get", (object_ref,))?;

    // Extract the result value
    let result_value: i32 = result.extract()?;
    println!("Result from ray.get: {}", result_value);

    Ok(())
}

#[pyfunction]
fn call_ray_get(py: Python, ray: &PyAny, node_list_ref: &PyAny) -> PyResult<()> {
    // Get the result using `ray.get`
    let result = ray.call_method1("get", (node_list_ref,))?;

    // Extract the result value as a Vec<i32>
    let result_value: Vec<i32> = result.extract()?;
    // println!("Result from ray.get: {:?}", result_value);
    Ok(())
}

#[pymodule]
#[allow(dead_code)]
fn roy_shmem(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<SharedMemory>()?;
    // m.add_function(wrap_pyfunction!(call_ray_get, m)?)?;
    m.add_function(wrap_pyfunction!(optimized_getitem, m)?)?;
    m.add_class::<Roylist>()?;
    Ok(())
}
