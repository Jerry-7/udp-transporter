from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
import os

def create_app(udp_client):
    app = Flask(__name__)
    socketio = SocketIO(app, cors_allowed_origins="*")

    UPLOAD_FOLDER = 'uploads'
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # 绑定udp_client回调，推送给前端
    def progress_cb(mode, done, total):
        socketio.emit('progress_update', {'mode': mode, 'done': done, 'total': total})

    def file_offer_cb(filename, total_chunks, file_hash):
        udp_client.awaiting_filename = filename  # 记录当前文件名，用于确认时发消息
        socketio.emit('file_offer', {
            'filename': filename,
            'total_chunks': total_chunks,
            'file_hash': file_hash
        })

    udp_client.progress_callback = progress_cb
    udp_client.file_offer_callback = file_offer_cb

    @socketio.on('file_accept')
    def on_file_accept(data):
        accept = data.get('accept', False)
        print("[DEBUG] 收到前端确认:", data)
        udp_client.accept_file_confirm(accept)

    @app.route("/")
    def index():
        return send_from_directory("templates", "index.html")

    @app.route("/clients", methods=["GET"])
    def get_clients():
        return jsonify(list(udp_client.clients))

    @app.route("/connect", methods=["POST"])
    def connect():
        data = request.json
        addr = data.get("address")
        if not addr:
            return jsonify({"error": "Missing address"}), 400
        udp_client.connect(addr)
        return jsonify({"message": f"Connected to {addr}"})

    @app.route("/sendfile", methods=["POST"])
    def send_file():
        if 'file' not in request.files or 'target' not in request.form:
            return jsonify({"error": "Missing file or target parameter"}), 400

        file = request.files['file']
        target = request.form['target']

        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        udp_client.send_file(target, filepath)
        return jsonify({"message": f"File sent to {target}"})

    return app, socketio
