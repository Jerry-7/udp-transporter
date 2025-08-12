import socket
import threading
import os
import hashlib
import time

CHUNK_SIZE = 1024
UPLOAD_FOLDER = 'uploads'

class UDPClient:
    def __init__(self, local_addr, progress_callback=None, file_offer_callback=None):
        ip, port = local_addr.split(':')
        self.local_ip = ip
        self.local_port = int(port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.local_ip, self.local_port))

        self.clients = set()
        self.progress_callback = progress_callback
        self.file_offer_callback = file_offer_callback

        # 状态相关
        self.awaiting_accept = False
        self.awaiting_filename = None
        self.accept_received = False
        self.reject_received = False

        self.recv_chunks = {}
        self.recv_meta = {}

    def start(self):
        threading.Thread(target=self.listen, daemon=True).start()

    def listen(self):
        while True:
            try:
                data, addr = self.sock.recvfrom(65536)
                self.handle_packet(data, addr)
            except Exception as e:
                print("[ERROR]", e)

    def handle_packet(self, data, addr):
        # 解码尝试，二进制chunk会导致decode失败，需要特殊处理
        try:
            msg = data.decode()
        except:
            msg = None

        if msg is not None:
            if msg.startswith("HELLO"):
                self.clients.add(f"{addr[0]}:{addr[1]}")
            elif msg.startswith("META::"):
                parts = msg.split("::")
                filename, total, file_hash = parts[1], int(parts[2]), parts[3]
                self.recv_meta[addr] = (filename, total, file_hash)
                self.recv_chunks[addr] = {}
                if self.file_offer_callback:
                    self.file_offer_callback(filename, total, file_hash)
            elif msg.startswith("ACCEPT::"):
                filename = msg.split("::")[1]
                if self.awaiting_accept and filename == self.awaiting_filename:
                    self.accept_received = True
                    self.awaiting_accept = False
            elif msg.startswith("REJECT::"):
                filename = msg.split("::")[1]
                if self.awaiting_accept and filename == self.awaiting_filename:
                    self.reject_received = True
                    self.awaiting_accept = False
            elif msg.startswith("CHUNK::"):
                # chunk后面跟的是二进制，不能用decode全取，需特殊处理
                parts = data.split(b"::", 3)
                index = int(parts[1].decode())
                total = int(parts[2].decode())
                content = parts[3]
                if addr in self.recv_chunks:
                    self.recv_chunks[addr][index] = content
                    if self.progress_callback:
                        self.progress_callback('receive', len(self.recv_chunks[addr]), total)
                    if len(self.recv_chunks[addr]) == total:
                        self.save_received_file(addr)
        else:
            # 数据无法用utf-8解码，认为是chunk分片
            parts = data.split(b"::", 3)
            if len(parts) == 4 and parts[0] == b"CHUNK":
                try:
                    index = int(parts[1].decode())
                    total = int(parts[2].decode())
                    content = parts[3]
                    if addr in self.recv_chunks:
                        self.recv_chunks[addr][index] = content
                        if self.progress_callback:
                            self.progress_callback('receive', len(self.recv_chunks[addr]), total)
                        if len(self.recv_chunks[addr]) == total:
                            self.save_received_file(addr)
                except Exception as e:
                    print("[ERROR] Chunk decode error:", e)

    def accept_file_confirm(self, accept):
        # 这里不再用事件等待，直接用UDP回信
        if accept:
            msg = f"ACCEPT::{self.awaiting_filename}"
        else:
            msg = f"REJECT::{self.awaiting_filename}"

        # 发送回去给发送方确认
        # 发送方地址存储在recv_meta对应的addr
        for addr, meta in self.recv_meta.items():
            if meta[0] == self.awaiting_filename:
                self.sock.sendto(msg.encode(), addr)
                break

    def connect(self, addr):
        ip, port = addr.split(':')
        port = int(port)
        self.sock.sendto(b"HELLO", (ip, port))
        self.clients.add(addr)

    def send_file(self, target, filepath):
        if not os.path.exists(filepath):
            print("[ERROR] File not found")
            return

        ip, port = target.split(':')
        port = int(port)
        with open(filepath, 'rb') as f:
            content = f.read()

        total = (len(content) + CHUNK_SIZE - 1) // CHUNK_SIZE
        file_hash = hashlib.md5(content).hexdigest()
        filename = os.path.basename(filepath)

        # 发送文件元信息
        meta_msg = f"META::{filename}::{total}::{file_hash}"
        self.sock.sendto(meta_msg.encode(), (ip, port))

        # 等待接收端确认
        self.awaiting_accept = True
        self.awaiting_filename = filename
        self.accept_received = False
        self.reject_received = False

        wait_time = 0
        while self.awaiting_accept and wait_time < 10:
            time.sleep(0.1)
            wait_time += 0.1

        if self.reject_received:
            print("[INFO] File offer rejected")
            return

        if not self.accept_received:
            print("[INFO] No response to file offer")
            return

        # 发送所有分片
        for i in range(total):
            chunk = content[i * CHUNK_SIZE:(i + 1) * CHUNK_SIZE]
            msg = f"CHUNK::{i}::{total}::".encode() + chunk
            self.sock.sendto(msg, (ip, port))
            if self.progress_callback:
                self.progress_callback('send', i + 1, total)
            time.sleep(0.01)

    def save_received_file(self, addr):
        filename, total, file_hash = self.recv_meta[addr]
        chunks = self.recv_chunks[addr]
        ordered = [chunks[i] for i in range(total)]
        content = b''.join(ordered)

        calc_hash = hashlib.md5(content).hexdigest()
        if calc_hash != file_hash:
            print("[ERROR] Hash mismatch! 文件校验失败")
            return

        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)

        filepath = os.path.join(UPLOAD_FOLDER, f"recv_{filename}")
        with open(filepath, 'wb') as f:
            f.write(content)
        print(f"[INFO] 文件已保存: {filepath}")
