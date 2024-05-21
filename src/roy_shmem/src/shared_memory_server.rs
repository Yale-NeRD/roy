use std::net::{UdpSocket, SocketAddr};
use std::collections::HashMap;
use std::sync::{Arc, Mutex, RwLock};
use crate::shared_memory::{MemoryState, CacheState, Message, Opcode};

pub struct SharedMemoryServer {
    pub data: Arc::<Mutex<HashMap<String, MemoryState>>>,
    pub server_addr: String,
    running: Arc::<RwLock::<bool>>,
}

impl SharedMemoryServer {
    pub fn new(server_addr: String) -> Self {
        SharedMemoryServer {
            data: Arc::new(Mutex::new(HashMap::new())),
            server_addr: server_addr,
            running: Arc::new(RwLock::new(false)),
        }
    }

    fn check_port(&self, socket_addr: SocketAddr) -> Result<(), std::io::Error> {
        let socket = UdpSocket::bind(socket_addr);
        if socket.is_err() {
            return Err(std::io::Error::new(std::io::ErrorKind::InvalidInput, "Failed to bind socket"));
        }
        // unbind
        drop(socket);
        Ok(())
    }

    pub fn start(&mut self) -> Result<(), std::io::Error> {
        // Parse the address string into a SocketAddr
        let socket_addr = self.server_addr.parse::<SocketAddr>();
        if socket_addr.is_err() {
            return Err(std::io::Error::new(std::io::ErrorKind::InvalidInput, "Invalid address"));
        }
        let socket_addr = socket_addr.unwrap();
        // check the address in use
        self.check_port(socket_addr.clone())?;
        
        // Wrap the necessary data in Arc<Mutex<>>.
        let data = Arc::new(Mutex::new(self.data.clone()));
        // let socket = Arc::new(Mutex::new());
        
        // Clone the Arcs for use in the thread.
        let data_clone = self.data.clone();
        let running_clone = self.running.clone();

        // std::thread::spawn(move || {
        //     let res = Self::serve_messages(data_clone, socket_addr.clone(), running_clone);
        //     if res.is_err() {
        //         eprintln!("Error: {:?}", res.unwrap_err());
        //     }
        // });
        let _res = Self::serve_messages(data_clone, socket_addr.clone(), running_clone);
        println!("Starting server at {}", self.server_addr);
        return Ok(());
    }

    pub fn check_server_status(&self) -> bool {
        *self.running.read().unwrap()
    }

    pub fn terminate_server(&self) {
        *self.running.write().unwrap() = false;
    }

    fn serve_messages(
        data: Arc<Mutex<HashMap<String, MemoryState>>>,
        socket_addr: SocketAddr,
        running: Arc<RwLock<bool>>)
        -> Result<(), std::io::Error> {
        println!("Binding server at {}", socket_addr);
        // Bind the socket to the specified address
        let socket = UdpSocket::bind(socket_addr)?;
        // assert socket status
        if socket.local_addr().is_err() {
            return Err(std::io::Error::new(std::io::ErrorKind::InvalidInput, "Failed to bind socket"));
        }
        let local_addr = socket.local_addr().unwrap();
        println!("Server started at {}", local_addr);
        *running.write().unwrap() = true;

        // Listen for incoming messages
        loop {
            if *running.read().unwrap() == false {
                break;
            }
            let mut buf = [0; 1024];
            let (bytes_read, client_addr) = socket.recv_from(&mut buf)?;
            let request = std::str::from_utf8(&buf[..bytes_read]);
            println!("Received request from {}: {}", client_addr, request.unwrap());
            if request.is_err() {
                return Err(std::io::Error::new(std::io::ErrorKind::InvalidInput, "Invalid request"));
            }
            let request: Message = bincode::deserialize(&buf[..bytes_read])
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
        
            match request.opcode {
                // Control messages
                Opcode::Init => {
                    println!("Received INIT message with body: {}", request.body);
                    let response = Message { opcode: Opcode::Ack, body: "OK".to_string() };
                    let response_bytes = bincode::serialize(&response).unwrap();
                    socket.send_to(&response_bytes, client_addr)?;
                },
                Opcode::Term => {
                    println!("Received TERMINATE message with body: {}", request.body);
                    *running.write().unwrap() = false;
                    break;
                },
                // Data messages
                Opcode::Read => {
                    println!("Received READ message with body: {}", request.body);
                    let data = data.lock().unwrap();
                    let response = match data.get(&request.body) {
                        Some(state) => {
                            if state.data.is_some() {
                                Message { opcode: Opcode::ReadResp, body: state.data.clone().unwrap() }
                            } else {
                                Message { opcode: Opcode::ReadNack, body: "Key not found".to_string() }
                            }
                        },
                        None => {
                            Message { opcode: Opcode::ReadNack, body: "Key not found".to_string() }
                        }
                    };
                    let response_bytes = bincode::serialize(&response).unwrap();
                    socket.send_to(&response_bytes, client_addr)?;
                },
                Opcode::Write => {
                    println!("Received WRITE message with body: {}", request.body);
                    let key_value: Vec<&str> = request.body.split(':').collect();
                    if key_value.len() != 2 {
                        // send ReadNack
                        let response = Message { opcode: Opcode::WriteNack, body: "Invalid key-value pair".to_string() };
                        let response_bytes = bincode::serialize(&response).unwrap();
                        socket.send_to(&response_bytes, client_addr)?;
                        continue;
                    }
                    let mut locked_data = data.lock().unwrap();
                    // insert new key-value pair
                    let new_state = MemoryState {
                        data: Some(key_value[1].to_string()),
                        state: CacheState::Modified
                    };
                    locked_data.insert(key_value[0].to_string(), new_state);
                    let response = Message { opcode: Opcode::WriteResp, body: "OK".to_string() };
                    let response_bytes = bincode::serialize(&response).unwrap();
                    socket.send_to(&response_bytes, client_addr)?;
                },
                _ => {
                    return Err(std::io::Error::new(std::io::ErrorKind::InvalidInput, "Invalid request"));
                }
            }
        }
        Ok(())
    }
}
