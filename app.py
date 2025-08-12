import sys
import os
from udp_core import UDPClient
from udp_flask_server import create_app

def main():
    if len(sys.argv) != 2:
        print("用法: python app.py <local_ip:port>")
        exit(1)

    local_addr = sys.argv[1]

    # 只在主进程绑定套接字
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or os.environ.get("FLASK_ENV") != "development":
        udp_client = UDPClient(local_addr=local_addr)
        udp_client.start()
    else:
        udp_client = None  # 热重载子进程中不绑定

    if udp_client is None:
        udp_client = UDPClient(local_addr=local_addr)

    app, socketio = create_app(udp_client)
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)

if __name__ == "__main__":
    main()
