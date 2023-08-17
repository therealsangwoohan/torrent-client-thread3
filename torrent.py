from threading import Thread
from queue import Queue
import hashlib
import time

import requests
from bcoding import bdecode, bencode

from piece import Work, Result, is_integral
from peer import Peer


class Torrent:
    def __init__(self, torrent_file_path: str) -> None:
        with open(torrent_file_path, "rb") as f:
            self.torrent_file = bdecode(f)

        self.tracker_urls = self._get_tracker_urls()
        self.info_hash = self._get_info_hash()
        self.name = self.torrent_file["info"]["name"]
        self.length = self.torrent_file["info"]["length"]
        self.piece_length = self.torrent_file["info"]["piece length"]
        self.piece_hashes = self._get_piece_hashes()
        self.peer_id = self._generate_peer_id()
        self.peers = self._request_peers()

    def _get_tracker_urls(self) -> list[str]:
        announce_list = self.torrent_file.get("announce-list", [])
        urls = []
        if len(announce_list) > 0:
            for announce in announce_list:
                urls.append(announce[0])
        else:
            urls.append(self.torrent_file["announce"])
        return urls

    def _get_info_hash(self) -> bytes:
        return hashlib.sha1(bencode(self.torrent_file["info"])).digest()

    def _get_piece_hashes(self) -> list[bytes]:
        raw_pieces = self.torrent_file["info"]["pieces"]
        piece_hashes = []
        for i in range(0, len(raw_pieces), 20):
            piece_hashes.append(raw_pieces[i:i+20])
        return piece_hashes

    def _generate_peer_id(self) -> bytes:
        seed = str(time.time())
        return hashlib.sha1(seed.encode('utf-8')).digest()

    def _request_peers(self) -> list[Peer]:
        port = 6881

        params = {
            "info_hash": self.info_hash,
            "peer_id": self.peer_id,
            "port": port,
            "uploaded": "0",
            "downloaded": "0",
            "left": self.length,
        }

        for url in self.tracker_urls:
            try:
                response = requests.get(url, params)
                peers = []
                peersDict = bdecode(response.content)["peers"]
                for peer in peersDict:
                    peers.append(Peer(peer["ip"], peer["port"]))
                return peers
            except Exception as e:
                print("Request failed:", e)
        return []

    def download(self, download_path: str) -> None:
        buffer = self._download_to_memory()
        with open(download_path, "wb+") as out_file:
            out_file.write(buffer)

    def _download_to_memory(self) -> bytearray:
        works: Queue[Work] = Queue()
        results: Queue[Result] = Queue()

        for piece_index, piece_hash in enumerate(self.piece_hashes):
            piece_length = self._get_piece_length(piece_index)
            works.put(Work(piece_index, piece_hash, piece_length))

        for peer in self.peers:
            work_thread = Thread(target=self._start_work,
                                 args=(peer, works, results))
            work_thread.start()

        buffer = bytearray(self.length)
        nb_of_downloaded_pieces = 0
        while nb_of_downloaded_pieces < len(self.piece_hashes):
            result = results.get()
            start, end = self._get_piece_bounds(result.index)
            buffer[start:end] = result.data
            nb_of_downloaded_pieces += 1
        return buffer

    def _get_piece_length(self, index: int) -> int:
        start, end = self._get_piece_bounds(index)
        return end - start

    def _get_piece_bounds(self, index: int) -> tuple[int, int]:
        start = index * self.piece_length
        end = start + self.piece_length
        if end > self.length:
            end = self.length
        return start, end

    def _start_work(self,
                    peer: Peer,
                    works: Queue[Work],
                    results: Queue[Result]) -> None:
        try:
            peer.connect()
            print(f"{peer} connected")
            peer.do_handshake(self.info_hash, self.peer_id)
            print(f"{peer} handshaked")
            peer.receive_bitfield()
            print(f"{peer} received bitfield")
            peer.send_unchoke()
            print(f"{peer} unchoke sended")
            peer.send_interested()
            print(f"{peer} interested sended")
        except Exception as e:
            print(f"Failed to connect to peer {peer}: {e}")
            return

        while True:
            work = works.get()

            if not peer.has_piece(work.piece_index):
                works.put(work)
                continue

            try:
                downloaded_piece = peer.download_piece(work)
                print(f"Piece downloaded from {peer}")
            except Exception as e:
                print(f"Failed to download piece {work.piece_index}: {e}")
                works.put(work)
                return

            if not is_integral(downloaded_piece, work.piece_hash):
                print("not integral")
                works.put(work)
                continue
            print("is integral")

            results.put(Result(work.piece_index, downloaded_piece))
