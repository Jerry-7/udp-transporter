import socket
import threading
import sys

clients = set()
lock = threading.Lock()


def get_client_list(exclude_addr=None):
    """生成客户端地址列表，排除当前注册者"""
    with lock:
        return ",".join(addr for addr in clients if addr != exclude_addr)


def server_loop(bind_ip, bind_port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((bind_ip, bind_port))
    print(f"🛰️  服务端已启动，监听 {bind_ip}:{bind_port}")

    while True:
        try:
            data, addr = sock.recvfrom(1024)
            message = data.decode().strip()
            client_id = f"{addr[0]}:{addr[1]}"

            if message == "register":
                with lock:
                    if client_id not in clients:
                        clients.add(client_id)
                        print(f"📥 新客户端注册：{client_id}")

                # 回复在线客户端列表
                client_list = get_client_list(exclude_addr=client_id)
                if client_list:
                    for c in clients:
                        if c == client_id:
                            continue
                        ip, port = c.split(":")
                        sock.sendto(client_list.encode(), (ip, int(port)))
                        print(f"📤 已通知 {c} 当前在线列表: {client_list}")

        except Exception as e:
            print(f"[服务端错误] {e}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python server.py <ip:port>")
        print("示例: python server.py 0.0.0.0:8888")
        sys.exit(1)

    ip_port = sys.argv[1]
    if ":" not in ip_port:
        print("请使用 ip:port 格式")
        sys.exit(1)

    ip, port = ip_port.split(":")
    port = int(port)

    server_loop(ip, port)
