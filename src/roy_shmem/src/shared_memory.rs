
use serde::{Serialize, Deserialize};
use std::net::SocketAddr;
use std::collections::HashSet;

pub const ROY_BUFFER_SIZE: usize = 1024 * 1024;

#[derive(Debug, PartialEq)]
pub enum CacheState {
    Shared,
    Modified,
    Locked,
    Invalid
}

pub struct MemoryState {
    pub data: Option<Vec<u8>>,
    pub state: CacheState,
    pub sharers: HashSet<SocketAddr>,
    pub waiters: Vec<SocketAddr>
}

// Messages
#[derive(Serialize, Deserialize, Debug, PartialEq, Clone, Copy)]
#[repr(u16)]
pub enum Opcode {
    // Initialize the connection
    Init = 1,
    // Data transfer
    Read = 2,
    Write = 3,
    ReadResp = 4,
    ReadNack = 5,
    WriteResp = 6,
    WriteNack = 7,
    ReadPickle = 8,     // response should be ReadResp, ReadNack
    WritePickle = 9,    // response should be WriteResp, WriteNack
    // Locking
    Lock = 51,          // request to grab a lock
    LockAcqd = 52,      // response indicating that lock is acquired
    LockWait = 53,      // response indicating that lock is not acquired
    Unlock = 54,        // request to release a lock
    UnlockResp = 55,    // response indicating that lock is released
    LockNack = 56,      // NACK for Lock and Unlock (something went wrong)
    // Application controls
    NewHandle = 101,
    NewHandleResp = 102,
    // Server controls
    Term = 126,         // Control message to terminate the server
    Ack = 127,
    Other(u16), // This can be used to handle other opcodes
}

#[derive(Serialize, Deserialize, Debug)]
pub struct Message {
    pub opcode: Opcode,
    pub handle: String,
    pub data: Option<Vec<u8>>,
}
