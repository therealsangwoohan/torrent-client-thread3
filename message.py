import socket
import struct
from enum import Enum


class MessageID(Enum):
    CHOKE = 0
    UNCHOKE = 1
    INTERESTED = 2
    NOT_INTERESTED = 3
    HAVE = 4
    BITFIELD = 5
    REQUEST = 6
    PIECE = 7
    CANCEL = 8


class Message:
    def __init__(self, id: MessageID, payload: bytes) -> None:
        self.id = id
        self.payload = payload

    def serialize(self) -> bytearray:
        length = len(self.payload) + 1
        buffer = bytearray(4 + length)
        struct.pack_into('>I', buffer, 0, length)
        buffer[4] = self.id.value
        if len(buffer) > 4:
            buffer[5:] = self.payload
        return buffer


def read(socket: socket.socket) -> Message:
    length_buffer = b""
    while len(length_buffer) < 4:
        data_chunk = socket.recv(4 - len(length_buffer))
        if len(data_chunk) == 0:
            break
        length_buffer += data_chunk

    if len(length_buffer) < 4:
        raise Exception("Failed to read message length")

    length = struct.unpack(">I", length_buffer)[0]
    if length == 0:
        raise Exception("Received keep-alive message")

    message = b""
    while len(message) < length:
        chunk = socket.recv(length - len(message))
        message += chunk
    message_id = MessageID(message[0])
    payload = message[1:]
    return Message(message_id, payload)


def format_request(index: int, begin: int, length: int) -> Message:
    payload = bytearray()
    payload.extend(struct.pack('>I', index))
    payload.extend(struct.pack('>I', begin))
    payload.extend(struct.pack('>I', length))
    return Message(MessageID.REQUEST, payload)


def parse_have(message: Message) -> int:
    return int(struct.unpack(">I", message.payload)[0])


def parse_piece(index: int, buffer: bytearray, message: Message) -> int:
    parsed_index = struct.unpack(">I", message.payload[0:4])[0]
    if parsed_index != index:
        raise Exception(f"Expected index {index}, but got {parsed_index}")

    begin = struct.unpack(">I", message.payload[4:8])[0]
    if begin >= len(buffer):
        raise Exception(f"Begin offset is too high: {begin} >= {len(buffer)}")

    data = message.payload[8:]
    if begin + len(data) > len(buffer):
        raise Exception("Data too long")

    buffer[begin:begin + len(data)] = data
    return len(data)
