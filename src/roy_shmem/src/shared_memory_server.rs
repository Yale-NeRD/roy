use std::net::{UdpSocket, SocketAddr};
use std::collections::{HashMap, HashSet};
use std::num::ParseIntError;
use std::sync::{Arc, Mutex, RwLock};
use crate::shared_memory::{MemoryState, CacheState, Message, Opcode, ROY_BUFFER_SIZE};

#[derive(Debug)]
pub struct HandleStore {
    pub handles: Vec<String>,
}

pub struct SharedMemoryServer {
    pub data: Arc::<Mutex<HashMap<String, MemoryState>>>,
    pub pickle_data: Arc::<Mutex<HashMap<String, MemoryState>>>,
    pub handle_store: Arc::<Mutex<HashMap<String, HandleStore>>>,
    pub server_addr: String,
    running: Arc::<RwLock::<bool>>,
}

impl SharedMemoryServer {
    pub fn new(server_addr: String) -> Self {
        SharedMemoryServer {
            data: Arc::new(Mutex::new(HashMap::new())),
            pickle_data: Arc::new(Mutex::new(HashMap::new())),
            handle_store: Arc::new(Mutex::new(HashMap::new())),
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
        // start main body loop
        println!("Starting server at {}", self.server_addr);
        let _res = Self::serve_messages(
            self.data.clone(),
            self.pickle_data.clone(),
            self.handle_store.clone(),
            socket_addr.clone(), self.running.clone());
        println!("Server terminated");
        return Ok(());
    }

    // pub fn check_server_status(&self) -> bool {
    //     *self.running.read().unwrap()
    // }

    // pub fn terminate_server(&self) {
    //     *self.running.write().unwrap() = false;
    // }

    fn hs_get_index_fron_handle(handle: &str) -> Result<usize, ParseIntError> {
        return handle.split(".").last().unwrap().parse::<usize>();
    }

    fn hs_get_the_last_index(handle_store: &HashMap<String, HandleStore>, handle: &str) -> usize {
        let handle_store = handle_store.get(handle);
        if handle_store.is_none() {
            return 0;
        }
        let handle_store = handle_store.unwrap();
        let mut last_unused_idx: usize = 0;
        for h in handle_store.handles.iter() {
            let idx = Self::hs_get_index_fron_handle(h);
            if idx.is_err() {
                continue;
            }
            let idx = idx.unwrap();
            if idx == last_unused_idx {
                last_unused_idx += 1;
            }
        }
        println!("Last unused index: {}", last_unused_idx);
        last_unused_idx
    }

    fn serve_messages(
        data: Arc<Mutex<HashMap<String, MemoryState>>>,
        pickle_data: Arc<Mutex<HashMap<String, MemoryState>>>,
        handle_store: Arc<Mutex<HashMap<String, HandleStore>>>,
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
        let mut buf: Box<[u8]> = vec![0; ROY_BUFFER_SIZE].into_boxed_slice();
        loop {
            if *running.read().unwrap() == false {
                break;
            }
            let (bytes_read, client_addr) = socket.recv_from(&mut buf)?;
            let request: Message = bincode::deserialize(&buf[..bytes_read])
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
            match request.opcode {
                // Control messages
                Opcode::Init => {
                    println!("Received INIT message with handle: {}", request.handle);
                    let response = Message {
                        opcode: Opcode::Ack,
                        handle: "".to_string(),
                        data: Some("OK".as_bytes().to_vec()) };
                    let response_bytes = bincode::serialize(&response).unwrap();
                    socket.send_to(&response_bytes, client_addr)?;
                },
                Opcode::Term => {
                    println!("Received TERMINATE message with handle: {}", request.handle);
                    *running.write().unwrap() = false;
                    break;
                },
                Opcode::NewHandle => {
                    println!("Received NEW_HANDLE message with handle: {}", request.handle);
                    // check handle store for existing handle
                    let mut handle_store = handle_store.lock().unwrap();
                    let handle = handle_store.get(&request.handle);
                    let new_handle;
                    // assign new handle with format [handle_name].0, [handle_name].1, ...
                    if handle.is_some() {
                        let last_idx = Self::hs_get_the_last_index(&handle_store, &request.handle);
                        new_handle = format!("{}.{}", request.handle, last_idx);
                        handle_store.get_mut(&request.handle).unwrap().handles.push(new_handle.clone());
                    } else {
                        let last_idx = 0;
                        new_handle = format!("{}.{}", request.handle, last_idx);
                        handle_store.insert(request.handle.clone(), HandleStore { handles: vec![new_handle.clone()] });
                    }
                    let response = Message { opcode: Opcode::NewHandleResp, handle: request.handle, data: Some(new_handle.as_bytes().to_vec()) };
                    let response_bytes = bincode::serialize(&response).unwrap();
                    socket.send_to(&response_bytes, client_addr)?;
                },
                // Data messages
                Opcode::Read => {
                    println!("Received READ message with handle: {}", request.handle);
                    let data = data.lock().unwrap();
                    let response = match data.get(&request.handle) {
                        Some(state) => {
                            if state.data.is_some() {
                                Message { opcode: Opcode::ReadResp, handle: request.handle, data: Some(state.data.clone().unwrap()) }
                            } else {
                                Message { opcode: Opcode::ReadNack, handle: request.handle, data: Some("Key not found".as_bytes().to_vec()) }
                            }
                        },
                        None => {
                            Message { opcode: Opcode::ReadNack, handle: request.handle, data: Some("Key not found".as_bytes().to_vec()) }
                        }
                    };
                    let response_bytes = bincode::serialize(&response).unwrap();
                    // println!("Sent response: {:?}", response);
                    socket.send_to(&response_bytes, client_addr)?;
                },
                Opcode::ReadPickle => {
                    Self::handle_read_pickle(&request, pickle_data.clone(), &socket, client_addr)?;
                },
                Opcode::Lock => {
                    Self::handle_read_lock(&request, pickle_data.clone(), &socket, client_addr)?;
                },
                Opcode::Write => {
                    println!("Received WRITE message with handle: {}", request.handle);
                    let handle = request.handle.clone();
                    let new_data = match request.data {
                        Some(new_data) => new_data,
                        None => {
                            // send WriteNack
                            let response = Message {
                                opcode: Opcode::WriteNack,
                                handle: request.handle,
                                data: Some("Invalid data to insert".as_bytes().to_vec()) };
                            let response_bytes = bincode::serialize(&response).unwrap();
                            socket.send_to(&response_bytes, client_addr)?;
                            continue;
                        }
                    };
                    let mut locked_data = data.lock().unwrap();
                    // insert new key-value pair
                    let new_state = MemoryState {
                        data: Some(new_data.clone()),
                        state: CacheState::Invalid, // data is written so no permision is granted
                        sharers: HashSet::new(),
                        waiters: Vec::new()
                    };
                    locked_data.insert(handle, new_state); 
                    let response = Message { opcode: Opcode::WriteResp, handle: request.handle, data: None };
                    let response_bytes = bincode::serialize(&response).unwrap();
                    // println!("Sent response: {:?}", response);
                    socket.send_to(&response_bytes, client_addr)?;
                },
                Opcode::WritePickle => {
                    Self::handle_write_pickle(&request, pickle_data.clone(), &socket, client_addr)?;
                },
                Opcode::Unlock => {
                    Self::handle_write_unlock(&request, pickle_data.clone(), &socket, client_addr)?;
                },
                _ => {
                    return Err(std::io::Error::new(std::io::ErrorKind::InvalidInput, "Invalid request"));
                }
            }
        }
        Ok(())
    }

    fn handle_read_pickle(
        request: &Message,
        pickle_data: Arc<Mutex<HashMap<String, MemoryState>>>,
        socket: &UdpSocket,
        client_addr: SocketAddr) -> Result<(), std::io::Error>
    {
        println!("Received READ_PICKLE message with handle: {}", request.handle);
        let pickle_data = pickle_data.lock().unwrap();
        let response = match pickle_data.get(&request.handle) {
            Some(state) => {
                if state.data.is_some() {
                    Message { opcode: Opcode::ReadResp, handle: request.handle.clone(), data: Some(state.data.clone().unwrap()) }
                } else {
                    Message { opcode: Opcode::ReadNack, handle: request.handle.clone(), data: Some("Key not found".as_bytes().to_vec()) }
                }
            },
            None => {
                Message { opcode: Opcode::ReadNack, handle: request.handle.clone(), data: Some("Key not found".as_bytes().to_vec()) }
            }
        };
        let response_bytes = bincode::serialize(&response).unwrap();
        // println!("Sent response: {:?}", response);
        socket.send_to(&response_bytes, client_addr)?;
        Ok(())
    }

    fn handle_write_pickle(
        request: &Message,
        pickle_data: Arc<Mutex<HashMap<String, MemoryState>>>,
        socket: &UdpSocket,
        client_addr: SocketAddr) -> Result<(), std::io::Error> 
    {
        println!("Received WRITE_PICKLE message with handle: {}", request.handle);
        let handle = request.handle.clone();
        // TODO: separate this data validity check into a function (check_write_data)
        let new_data = match request.data.clone() {
            Some(new_data) => new_data,
            None => {
                // send WriteNack
                let response = Message {
                    opcode: Opcode::WriteNack,
                    handle: request.handle.clone(),
                    data: Some("Invalid data to insert".as_bytes().to_vec()) };
                let response_bytes = bincode::serialize(&response).unwrap();
                let _res = socket.send_to(&response_bytes, client_addr);
                return Ok(());
            }
        };
        let mut locked_data = pickle_data.lock().unwrap();
        // insert new key-value pair
        let new_state = MemoryState {
            data: Some(new_data.clone()),
            state: CacheState::Invalid,
            sharers: HashSet::new(),
            waiters: Vec::new()
        };
        locked_data.insert(handle, new_state); 
        let response = Message { opcode: Opcode::WriteResp, handle: request.handle.clone(), data: None };
        let response_bytes = bincode::serialize(&response).unwrap();
        // println!("Sent response: {:?}", response);
        let _res = socket.send_to(&response_bytes, client_addr);
        return Ok(());
    }

    fn handle_read_lock(
        request: &Message,
        pickle_data: Arc<Mutex<HashMap<String, MemoryState>>>,
        socket: &UdpSocket,
        client_addr: SocketAddr) -> Result<(), std::io::Error>
    {
        println!("Received READ_LOCK message with handle: {}", request.handle);
        // checking the locking method
        if request.data.is_none() {
            let response = Message { opcode: Opcode::LockNack, handle: request.handle.clone(), data: Some("Invalid lock request".as_bytes().to_vec()) };
            let response_bytes = bincode::serialize(&response).unwrap();
            // println!("Sent response: {:?}", response);
            socket.send_to(&response_bytes, client_addr)?;
            return Ok(());
        }
        let locking_method = String::from_utf8(request.data.clone().unwrap());
        println!("Locking method: {:?}", locking_method);
        let mut pickle_data = pickle_data.lock().unwrap();
        let response = match pickle_data.get_mut(&request.handle) {
            Some(state) => {
                // TODO: set proper state for the lock
                // Mutex
                if state.state == CacheState::Invalid {
                    state.state = CacheState::Modified;
                    state.sharers.insert(client_addr);
                    if state.data.is_some() {
                        Message { opcode: Opcode::LockAcqd, handle: request.handle.clone(), data: Some(state.data.clone().unwrap()) }
                    } else {
                        Message { opcode: Opcode::LockNack, handle: request.handle.clone(), data: Some("Key not found".as_bytes().to_vec()) }
                    }
                } else {
                    // Add this client to the waiting list
                    // - check if the client is already in the waiting list\
                    if !state.waiters.contains(&client_addr) {
                        state.waiters.push(client_addr);
                    }
                    Message { opcode: Opcode::LockWait, handle: request.handle.clone(), data: Some("".as_bytes().to_vec()) }
                }
            },
            None => {
                Message { opcode: Opcode::LockNack, handle: request.handle.clone(), data: Some("Key not found".as_bytes().to_vec()) }
            }
        };
        let response_bytes = bincode::serialize(&response).unwrap();
        // println!("Sent response: {:?}", response);
        socket.send_to(&response_bytes, client_addr)?;
        Ok(())
    }

    fn handle_write_unlock (
        request: &Message,
        pickle_data: Arc<Mutex<HashMap<String, MemoryState>>>,
        socket: &UdpSocket,
        client_addr: SocketAddr) -> Result<(), std::io::Error> 
    {
        println!("Received WRITE_UNLOCK message with handle: {}", request.handle);
        let handle = request.handle.clone();
        let new_data = match request.data.clone() {
            Some(new_data) => new_data,
            None => {
                // send WriteNack
                let response = Message {
                    opcode: Opcode::LockNack,
                    handle: request.handle.clone(),
                    data: Some("Invalid data to insert".as_bytes().to_vec()) };
                let response_bytes = bincode::serialize(&response).unwrap();
                let _res = socket.send_to(&response_bytes, client_addr);
                return Ok(());
            }
        };
        let mut locked_data = pickle_data.lock().unwrap();
        // get the current state as mutable
        let state = locked_data.get_mut(&handle);
        if state.is_none() {
            // insert new key-value pair
            let new_state = MemoryState {
                data: Some(new_data.clone()),
                state: CacheState::Invalid,
                sharers: HashSet::new(),
                waiters: Vec::new()
            };
            locked_data.insert(handle, new_state); 
        } else {
            let state = state.unwrap();
            state.data = Some(new_data.clone());
            if state.sharers.contains(&client_addr) {
                state.sharers.remove(&client_addr);
                if state.state == CacheState::Modified {
                    state.state = CacheState::Invalid;
                }
                // Check waiter list and notify the next client
                if state.waiters.len() > 0 {
                    let next_client = state.waiters.remove(0);
                    let response = Message { opcode: Opcode::LockAcqd, handle: request.handle.clone(), data: Some(state.data.clone().unwrap()) };
                    let response_bytes = bincode::serialize(&response).unwrap();
                    // println!("Sent response: {:?}", response);
                    let _res = socket.send_to(&response_bytes, next_client);
                    println!("Notified the next client: {:?}, data: {}", next_client, state.data.clone().unwrap().len());
                }
            }
        }
        let response = Message { opcode: Opcode::UnlockResp, handle: request.handle.clone(), data: None };
        let response_bytes = bincode::serialize(&response).unwrap();
        // println!("Sent response: {:?}", response);
        let _res = socket.send_to(&response_bytes, client_addr);
        return Ok(());
    }

}
