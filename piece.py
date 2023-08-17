import hashlib


class Work:
    def __init__(self,
                 piece_index: int,
                 piece_hash: bytes,
                 piece_length: int) -> None:
        self.piece_index = piece_index
        self.piece_hash = piece_hash
        self.piece_length = piece_length


class Result:
    def __init__(self, index: int, data: bytes) -> None:
        self.index = index
        self.data = data


class WorkProgress:
    def __init__(self, work: Work) -> None:
        self.work = work
        self.buffer = bytearray(work.piece_length)
        self.downloaded = 0
        self.backlog = 0
        self.requested = 0


def is_integral(downloaded_piece: bytes, piece_hash: bytes) -> bool:
    hash_result = hashlib.sha1(downloaded_piece).digest()
    if hash_result != piece_hash:
        return False
    return True
