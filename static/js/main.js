const socket = io();

// 接收文件请求弹窗展示
socket.on("file_offer", (data) => {
  document.getElementById("incomingFileOffer").style.display = "block";
  document.getElementById("offerFilename").innerText = data.filename;
  document.getElementById("offerTotalChunks").innerText = data.total_chunks;
  document.getElementById("offerHash").innerText = data.file_hash;

  document.getElementById("acceptFileBtn").onclick = () => {
    socket.emit("file_accept", { accept: true });
    document.getElementById("incomingFileOffer").style.display = "none";
  };

  document.getElementById("rejectFileBtn").onclick = () => {
    socket.emit("file_accept", { accept: false });
    document.getElementById("incomingFileOffer").style.display = "none";
  };
});

// 实时显示发送和接收进度
socket.on("progress_update", (data) => {
  const el = document.getElementById(
    data.mode === "send" ? "sendProgress" : "recvProgress"
  );
  el.innerText = `${data.mode === "send" ? "发送" : "接收"}进度: ${data.done}/${data.total}`;
});

// 连接按钮逻辑
function connect() {
  const addr = document.getElementById("inputAddress").value;
  if (!addr) return alert("请输入目标客户端地址（例如 192.168.0.101:9595）");

  fetch("/connect", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ address: addr })
  })
    .then(res => res.json())
    .then(data => {
      alert(data.message || "连接成功");
      loadClients();
    })
    .catch(err => alert("连接失败：" + err));
}

// 加载客户端列表
function loadClients() {
  fetch("/clients")
    .then(res => res.json())
    .then(clients => {
      const list = document.getElementById("clientsList");
      const sel = document.getElementById("targetSelect");

      list.innerHTML = "";
      sel.innerHTML = "";

      clients.forEach(c => {
        const li = document.createElement("li");
        li.innerText = c;
        list.appendChild(li);

        const opt = document.createElement("option");
        opt.value = c;
        opt.innerText = c;
        sel.appendChild(opt);
      });
    });
}

// 发送文件
function sendFile() {
  const file = document.getElementById("fileInput").files[0];
  const target = document.getElementById("targetSelect").value;
  if (!file || !target) return alert("请选择文件和目标客户端");

  const form = new FormData();
  form.append("file", file);
  form.append("target", target);

  fetch("/sendfile", {
    method: "POST",
    body: form
  })
    .then(res => res.json())
    .then(data => alert(data.message || "文件发送成功"))
    .catch(err => alert("发送失败：" + err));
}

// 页面加载时初始化
window.onload = () => {
  loadClients();

  document.getElementById("btnConnect").onclick = connect;
  document.getElementById("sendFileForm").onsubmit = (e) => {
    e.preventDefault();
    sendFile();
  };
};
