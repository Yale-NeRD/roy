use std::net::{IpAddr, Ipv4Addr, UdpSocket, SocketAddr};
use crate::shared_memory::{Message, Opcode};

pub struct SharedMemoryClient {
    pub socket: Option<UdpSocket>,
    pub server_ip_addr: String,
}

impl SharedMemoryClient {
    pub fn new(server_ip_addr: String) -> Self {
        SharedMemoryClient {
            socket: None,
            server_ip_addr: server_ip_addr,
        }
    }

    pub fn connect(&mut self) -> Result<(), std::io::Error> {
        println!("Connecting to server at {}", self.server_ip_addr);
        // Parse the address string into a SocketAddr
        let socket_addr = self.server_ip_addr.parse::<SocketAddr>();
        if socket_addr.is_err() {
            return Err(std::io::Error::new(std::io::ErrorKind::InvalidInput, "Invalid address"));
        }
        let socket_addr = socket_addr.unwrap();
        
        // Create a socket to communicate with the server
        let local_addr = SocketAddr::new(IpAddr::V4(Ipv4Addr::LOCALHOST), 0);
        let socket = UdpSocket::bind(local_addr);
        if socket.is_err() {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidInput,
                "Failed to bind local address"));
        }
        let socket = socket.unwrap();
        let res = socket.connect(socket_addr);
        if res.is_err() {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidInput,
                "Failed to connect to server"));
        }
        self.socket = Some(socket);
    
        // TODO: send a message to the server to initialize the connection
        // Send initialization message
        self.send_message(Opcode::Init, "Init message", None)?;
        println!("Waiting for response from server");

        // Wait for response
        let msg = self.recv_message()?;
        if msg.opcode != Opcode::Ack {
            return Err(std::io::Error::new(std::io::ErrorKind::InvalidData, "Invalid response"));
        }
        return Ok(());
    }

    pub fn send_terminate_message(&self) -> Result<(), std::io::Error> {
        self.send_message(Opcode::Term, "Terminate message", None)
    }

    pub fn read_data(&self, key: &str) -> Result<String, std::io::Error> {
        self.send_message(Opcode::Read, key, None)?;
        let msg = self.recv_message()?;
        if msg.opcode != Opcode::ReadResp || !msg.data.is_some(){
            return Err(std::io::Error::new(std::io::ErrorKind::InvalidData, "Invalid response"));
        }
        Ok(msg.data.unwrap())
    }

    pub fn write_data(&self, key: &str, value: &str) -> Result<(), std::io::Error> {
        self.send_message(Opcode::Write, key, Some(value))?;
        let resp = self.recv_message()?;
        if resp.opcode != Opcode::WriteResp {
            return Err(std::io::Error::new(std::io::ErrorKind::InvalidData, "Invalid response"));
        }
        Ok(())
    }

    fn send_message(&self, opcode: Opcode, handle: &str, data: Option<&str>) -> Result<(), std::io::Error> {
        let socket = self.socket.as_ref().unwrap();
        let message = Message {
            opcode: opcode,
            handle: handle.to_string(),
            data: data.map(|s| s.to_string()),
        };
        let message_bytes = bincode::serialize(&message).unwrap();
        socket.send(&message_bytes)?;
        Ok(())
    }

    fn recv_message(&self) -> Result<Message, std::io::Error> {
        let mut buf = [0; 1024];
        let socket = self.socket.as_ref().unwrap();
        let (bytes_read, _) = socket.recv_from(&mut buf)?;
        let message = bincode::deserialize(&buf[..bytes_read])
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
        Ok(message)
    }
}

