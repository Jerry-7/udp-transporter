import socket
import threading
import hashlib
import os
import sys
import time
import shlex

CHUNK_SIZE = 1024  # 每块文件数据大小（字节）
MISSING_RETRY_DELAY = 5  # 秒

class UDPClient:
    def __init__(self, server_addr=None, local_addr="0.0.0.0:9596"):
        self.server_ip, self.server_port = (server_addr.split(":") if server_addr else (None, None))
        self.local_ip, self.local_port = local_addr.split(":")
        self.local_port = int(self.local_port)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", self.local_port))

        self.clients = set()
        self.file_recv_buffer = {}
        self.expected_file_info = None
        self.lock = threading.Lock()
        self.relay_mode = self.server_ip is not None

    def register(self):
        if self.relay_mode:
            self.sock.sendto(b"register", (self.server_ip, int(self.server_port)))

    def start(self):
        threading.Thread(target=self.listen, daemon=True).start()
        if self.relay_mode:
            self.register()
        self.cmd_loop()

    def listen(self):
        while True:
            try:
                data, addr = self.sock.recvfrom(65535)
                print(f"[DEBUG] 接收到来自 {addr} 的数据: {data[:50]}")
                if data.startswith(b"FILE:"):
                    message = data.decode(errors="ignore").strip()
                    parts = message.split(":")
                    if len(parts) == 4:
                        filename, total_chunks, file_hash = parts[1], int(parts[2]), parts[3]

                        print(f"\n📥 收到文件传输请求：'{filename}'（共 {total_chunks} 块）")
                        confirm = input("❓ 是否接受该文件？[y/N]: ").strip().lower()

                        if confirm != "y":
                            print("🚫 拒绝接收该文件。")
                            with self.lock:
                                self.expected_file_info = None
                                self.file_recv_buffer = {}
                            continue

                        with self.lock:
                            self.expected_file_info = (filename, total_chunks, file_hash)
                            self.file_recv_buffer = {}
                            self.sender_addr = addr

                        threading.Thread(target=self.detect_missing_chunks, daemon=True).start()

                elif data.startswith(b"MISSING:"):
                    missing_parts = data.decode().split(":")[1]
                    missing_chunks = [int(i) for i in missing_parts.split(",") if i.strip().isdigit()]
                    self.resend_chunks(missing_chunks, addr)

                else:
                    try:
                        prefix_end = data.index(b"::")
                        prefix = data[:prefix_end].decode()
                        chunk_no = int(prefix)
                        chunk_data = data[prefix_end + 2:]

                        with self.lock:
                            if self.expected_file_info is None:
                                continue
                            self.file_recv_buffer[chunk_no] = chunk_data
                            print(f"📦 收到块 {chunk_no}")
                    except Exception as e:
                        print(f"[接收错误] {e}")

            except Exception as e:
                print(f"[网络错误] {e}")

    def detect_missing_chunks(self):
        time.sleep(MISSING_RETRY_DELAY)
        with self.lock:
            if not self.expected_file_info:
                return
            filename, total_chunks, file_hash = self.expected_file_info
            received_chunks = set(self.file_recv_buffer.keys())
            missing = [i for i in range(total_chunks) if i not in received_chunks]

            if not missing:
                print("✅ 所有块已接收，准备保存文件")
                self.save_file()
                return

            print(f"❗ 缺失块: {missing}")
            header = f"MISSING:{','.join(map(str, missing))}"
            self.sock.sendto(header.encode(), self.sender_addr)
            threading.Thread(target=self.detect_missing_chunks, daemon=True).start()

    def resend_chunks(self, chunk_list, addr):
        if not hasattr(self, 'last_sent_file'):
            return

        filename, filepath = self.last_sent_file
        print(f"🔁 重发块: {chunk_list}")
        with open(filepath, "rb") as f:
            for i in chunk_list:
                f.seek(i * CHUNK_SIZE)
                chunk = f.read(CHUNK_SIZE)
                packet = f"{i}::".encode() + chunk
                self.sock.sendto(packet, addr)
                time.sleep(0.01)

    def save_file(self):
        filename, total_chunks, expected_hash = self.expected_file_info
        file_path = "recv_" + filename
        with open(file_path, "wb") as f:
            for i in range(total_chunks):
                f.write(self.file_recv_buffer[i])

        actual_hash = self.sha256sum(file_path)
        if actual_hash == expected_hash:
            print(f"✅ 文件保存成功: {file_path}")
        else:
            print(f"❌ 哈希校验失败，文件已删除")
            os.remove(file_path)

        with self.lock:
            self.file_recv_buffer = {}
            self.expected_file_info = None

    def cmd_loop(self):
        while True:
            try:
                cmd_line = input("\n📥 输入命令 (sendfile ip:port filepath / connect ip:port / exit): ").strip()
                if not cmd_line:
                    continue
                parts = shlex.split(cmd_line)
                if parts[0] == "exit":
                    print("👋 再见")
                    os._exit(0)
                elif parts[0] == "sendfile" and len(parts) == 3:
                    self.send_file(parts[1], parts[2])
                elif parts[0] == "connect" and len(parts) == 2:
                    print(f"🔗 已连接至客户端 {parts[1]}")
                    self.clients.add(parts[1])
                else:
                    print("❗ 格式错误，应为: sendfile ip:port filepath 或 connect ip:port")
            except KeyboardInterrupt:
                print("\n👋 再见")
                break

    def send_file(self, target_client, filepath):
        if not os.path.isfile(filepath):
            print(f"❌ 文件 '{filepath}' 不存在")
            return

        file_size = os.path.getsize(filepath)
        total_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE
        file_hash = self.sha256sum(filepath)

        header = f"FILE:{os.path.basename(filepath)}:{total_chunks}:{file_hash}".encode()
        ip, port = target_client.split(":")
        addr = (ip, int(port))
        self.sock.sendto(header, addr)

        with open(filepath, "rb") as f:
            for i in range(total_chunks):
                chunk = f.read(CHUNK_SIZE)
                packet = f"{i}::".encode() + chunk
                self.sock.sendto(packet, addr)
                print(f"[DEBUG] 发送第 {i} 块完成，共 {total_chunks} 块，大小 {len(chunk)} 字节")
                time.sleep(0.01)

        self.last_sent_file = (os.path.basename(filepath), filepath)
        print(f"📤 文件发送完成，共 {total_chunks} 块")

    def sha256sum(self, filepath):
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()


if __name__ == "__main__":
    if len(sys.argv) != 2 and len(sys.argv) != 3:
        print("用法: python client.py <local_ip:port> [<server_ip:port>]")
        print("示例: python client.py 0.0.0.0:9596 192.168.1.100:8888")
        sys.exit(1)

    if len(sys.argv) == 3:
        client = UDPClient(server_addr=sys.argv[2], local_addr=sys.argv[1])
    else:
        client = UDPClient(server_addr=None, local_addr=sys.argv[1])

    client.start()
