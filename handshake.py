from struct import pack


class Handshake:
    def __init__(self, info_hash: bytes, peer_id: bytes) -> None:
        self.info_hash = info_hash
        self.peer_id = peer_id

    def convert_to_bytes(self) -> bytes:
        protocol = b"BitTorrent protocol"
        reserved = b"\x00" * 8
        handshake = pack(">B{}s8s20s20s".format(len(protocol)),
                         len(protocol),
                         protocol,
                         reserved,
                         self.info_hash,
                         self.peer_id)
        return handshake
