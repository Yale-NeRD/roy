use pyo3::prelude::*;
use std::thread;
use std::sync::{Arc, Mutex};

#[pyclass]
struct RustLib {
    running: Arc<Mutex<bool>>,
}

#[pymethods]
impl RustLib {
    #[new]
    fn new() -> Self {
        RustLib {
            running: Arc::new(Mutex::new(false)),
        }
    }

    fn start_daemon(&self) -> PyResult<()> {
        let running = self.running.clone();
        thread::spawn(move || {
            let mut running_guard = running.lock().unwrap();
            *running_guard = true;
            drop(running_guard);
            while *running.lock().unwrap() {
                // Daemon task
                println!("Daemon running...");
                thread::sleep(std::time::Duration::from_secs(5));
            }
            println!("Daemon stopped.");
        });
        Ok(())
    }

    fn stop_daemon(&self) -> PyResult<()> {
        let mut running_guard = self.running.lock().unwrap();
        *running_guard = false;
        Ok(())
    }

    fn is_running(&self) -> PyResult<bool> {
        let running_guard = self.running.lock().unwrap();
        Ok(*running_guard)
    }
}

#[pymodule]
#[allow(dead_code)]
fn roy_ctrl(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<RustLib>()?;
    Ok(())
}
