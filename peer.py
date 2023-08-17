import socket

from handshake import Handshake
import message
from piece import Work, WorkProgress


class Peer:
    def __init__(self, ip: str, port: int) -> None:
        self.ip = ip
        self.port = port
        self.is_choking_client = True

    def __repr__(self) -> str:
        return f"Peer({self.ip}, {self.port})"

    def connect(self) -> None:
        self.socket = socket.create_connection((self.ip, self.port), timeout=3)

    def do_handshake(self, info_hash: bytes, peer_id: bytes) -> None:
        handshake = Handshake(info_hash, peer_id)
        buffer = handshake.convert_to_bytes()
        self.socket.send(buffer)
        handshake = self.receive_handshake()
        if handshake.info_hash != info_hash:
            raise Exception("Received wrong info_hash")

    def receive_handshake(self) -> Handshake:
        length_buffer = self.socket.recv(1)
        pstrlen = int(length_buffer[0])

        if pstrlen == 0:
            raise ValueError("pstrlen cannot be 0")

        handshake_buffer = bytearray(48 + pstrlen)
        self.socket.recv_into(handshake_buffer)

        info_hash = bytes(handshake_buffer[pstrlen + 8: pstrlen + 8 + 20])
        peer_id = bytes(handshake_buffer[pstrlen + 8 + 20:])
        handshake = Handshake(info_hash, peer_id)
        return handshake

    def receive_bitfield(self) -> None:
        msg = message.read(self.socket)
        self.bitfield = bytearray(msg.payload)

    def send_unchoke(self) -> None:
        msg = message.Message(message.MessageID.UNCHOKE, b"")
        self.socket.send(msg.serialize())

    def send_interested(self) -> None:
        msg = message.Message(message.MessageID.INTERESTED, b"")
        self.socket.send(msg.serialize())

    def send_request(self, index: int, begin: int, length: int) -> None:
        msg = message.format_request(index, begin, length)
        self.socket.send(msg.serialize())

    def has_piece(self, index: int) -> bool:
        byte_index = index // 8
        offset = index % 8

        if not (0 <= byte_index < len(self.bitfield)):
            return False
        return (self.bitfield[byte_index] >> (7 - offset)) & 1 != 0

    def set_piece(self, index: int) -> None:
        byte_index = index // 8
        offset = index % 8

        if not (0 <= byte_index < len(self.bitfield)):
            return
        self.bitfield[byte_index] |= 1 << (7 - offset)

    def download_piece(self, work: Work) -> bytes:
        MAX_BLOCK_SIZE = 16384
        MAX_BACKLOG = 5
        state = WorkProgress(work)

        while state.downloaded < work.piece_length:
            if not self.is_choking_client:
                while state.backlog < MAX_BACKLOG and \
                      state.requested < work.piece_length:
                    block_size = MAX_BLOCK_SIZE
                    if work.piece_length - state.requested < block_size:
                        block_size = work.piece_length - state.requested
                    self.send_request(work.piece_index,
                                      state.requested,
                                      block_size)
                    state.backlog += 1
                    state.requested += block_size
            self.read_message(state)
        return state.buffer

    def read_message(self, state: WorkProgress) -> None:
        msg = message.read(self.socket)

        if msg.id == message.MessageID.UNCHOKE:
            self.is_choking_client = False
        elif msg.id == message.MessageID.CHOKE:
            self.is_choking_client = True
        elif msg.id == message.MessageID.HAVE:
            index = message.parse_have(msg)
            self.set_piece(index)
        elif msg.id == message.MessageID.PIECE:
            n = message.parse_piece(state.work.piece_index, state.buffer, msg)
            state.downloaded += n
            state.backlog -= 1
