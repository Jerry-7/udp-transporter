import sys
from udp_core import UDPClient
from udp_flask_server import create_app

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("\n用法: python main.py <local_ip:port>")
        print("示例: python main.py 0.0.0.0:9596\n")
        exit(1)

    local_addr = sys.argv[1]

    # 初始化 UDPClient
    client = UDPClient(local_addr=local_addr)
    client.start()

    # 创建 Flask app 和 SocketIO 实例
    app, socketio = create_app(client)

    # 启动 SocketIO + Flask
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, use_reloader=False)
