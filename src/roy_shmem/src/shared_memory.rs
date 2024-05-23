
use serde::{Serialize, Deserialize};

pub enum CacheState {
    Shared,
    Modified,
    Locked,
    Invalid
}

pub struct MemoryState {
    pub data: Option<Vec<u8>>,
    pub state: CacheState,
    
}

// Messages
#[derive(Serialize, Deserialize, Debug, PartialEq)]
#[repr(u8)]
pub enum Opcode {
    Init = 1,
    Read = 2,
    Write = 3,
    ReadResp = 4,
    ReadNack = 5,
    WriteResp = 6,
    WriteNack = 7,
    ReadPickle = 8,     // response should be ReadResp, ReadNack
    WritePickle = 9,    // response should be WriteResp, WriteNack
    NewHandle = 101,
    NewHandleResp = 102,
    Term = 126,
    Ack = 127,
    Other(u8), // This can be used to handle other opcodes
}

#[derive(Serialize, Deserialize, Debug)]
pub struct Message {
    pub opcode: Opcode,
    pub handle: String,
    pub data: Option<Vec<u8>>,
}
