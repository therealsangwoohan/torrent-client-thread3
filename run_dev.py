from torrent import Torrent

torrent_file_path = "../torrent_files/debian-12.0.0-amd64-netinst.iso.torrent"
download_path = "/Users/sangwoohan/Downloads/debian.iso"

torrent = Torrent(torrent_file_path)

torrent.download(download_path)
