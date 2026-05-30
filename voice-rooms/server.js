// voice-rooms シグナリングサーバ (v0.2)
// 役割: 静的配信 + 部屋管理(タグ付き) + WebRTC シグナリング中継 + 部屋内ブロードキャスト(chat/hand)
// 音声自体は通さない。声は各クライアント間の P2P(WebRTC mesh)で直接流れる。

import http from 'http';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { WebSocketServer } from 'ws';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PUBLIC = path.join(__dirname, 'public');
const PORT = process.env.PORT || 8800;

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
};

// ICE 設定: STUN は常時、TURN は環境変数があれば付与（鍵をクライアントに焼かない）
// 例: TURN_URLS="turn:turn.example:3478,turns:turn.example:5349" TURN_USERNAME=... TURN_CREDENTIAL=...
function iceServers() {
  const list = [{ urls: 'stun:stun.l.google.com:19302' }];
  if (process.env.TURN_URLS) {
    list.push({
      urls: process.env.TURN_URLS.split(',').map((s) => s.trim()).filter(Boolean),
      username: process.env.TURN_USERNAME || '',
      credential: process.env.TURN_CREDENTIAL || '',
    });
  }
  return list;
}

const server = http.createServer((req, res) => {
  let urlPath = decodeURIComponent(req.url.split('?')[0]);
  if (urlPath === '/ice') {
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
    res.end(JSON.stringify({ iceServers: iceServers() }));
    return;
  }
  if (urlPath === '/') urlPath = '/index.html';
  const filePath = path.join(PUBLIC, path.normalize(urlPath));
  if (!filePath.startsWith(PUBLIC)) { res.writeHead(403); res.end('Forbidden'); return; }
  fs.readFile(filePath, (err, data) => {
    if (err) { res.writeHead(404); res.end('Not found'); return; }
    res.writeHead(200, { 'Content-Type': MIME[path.extname(filePath)] || 'application/octet-stream' });
    res.end(data);
  });
});

const wss = new WebSocketServer({ server });

let nextId = 1;
const clients = new Map(); // id -> { ws, room, nick, tags }
const rooms = new Map();    // name -> { members:Set<id>, tags:[], host:id }

const send = (ws, obj) => { if (ws.readyState === 1) ws.send(JSON.stringify(obj)); };
const roomList = () => [...rooms.entries()].map(([name, r]) => ({ name, count: r.members.size, tags: r.tags }));
const broadcastRooms = () => { for (const c of clients.values()) send(c.ws, { type: 'rooms', rooms: roomList() }); };

function leaveRoom(id) {
  const me = clients.get(id);
  if (!me || !me.room) return;
  const r = rooms.get(me.room);
  if (r) {
    r.members.delete(id);
    for (const pid of r.members) send(clients.get(pid).ws, { type: 'peer-left', id });
    if (r.members.size === 0) rooms.delete(me.room);
    else if (r.host === id) { r.host = r.members.values().next().value; // ホストが抜けたら委譲
      for (const pid of r.members) send(clients.get(pid).ws, { type: 'host', id: r.host }); }
  }
  me.room = null;
}

// WebSocket ハートビート: プロキシ(Cloudflare 等)が idle WS を ~100秒で切るため 25秒ごとに ping/pong
function heartbeat() { this.isAlive = true; }
const HEARTBEAT = setInterval(() => {
  for (const ws of wss.clients) {
    if (ws.isAlive === false) { ws.terminate(); continue; }
    ws.isAlive = false;
    try { ws.ping(); } catch { /* noop */ }
  }
}, 25000);
wss.on('close', () => clearInterval(HEARTBEAT));

wss.on('connection', (ws) => {
  const id = String(nextId++);
  ws.isAlive = true;
  ws.on('pong', heartbeat);
  clients.set(id, { ws, room: null, nick: null, tags: [] });
  send(ws, { type: 'welcome', id, rooms: roomList() });

  ws.on('message', (raw) => {
    let msg; try { msg = JSON.parse(raw); } catch { return; }
    const me = clients.get(id);
    if (!me) return;

    switch (msg.type) {
      case 'join': {
        leaveRoom(id);
        const room = String(msg.room || '').slice(0, 40).trim();
        if (!room) return;
        me.room = room;
        me.nick = String(msg.nick || '').slice(0, 24);
        me.tags = Array.isArray(msg.tags) ? msg.tags.slice(0, 6).map((t) => String(t).slice(0, 16)) : [];
        let r = rooms.get(room);
        if (!r) { r = { members: new Set(), tags: me.tags.slice(0, 4), host: id }; rooms.set(room, r); }
        const peers = [...r.members].map((pid) => ({ id: pid, nick: clients.get(pid).nick }));
        send(ws, { type: 'peers', peers, host: r.host });
        for (const pid of r.members) send(clients.get(pid).ws, { type: 'peer-joined', id, nick: me.nick });
        r.members.add(id);
        broadcastRooms();
        break;
      }
      case 'signal': {
        const t = clients.get(msg.to);
        if (t) send(t.ws, { type: 'signal', from: id, data: msg.data });
        break;
      }
      case 'room': {
        // 同室全員へ broadcast（chat / hand）
        if (!me.room) return;
        const r = rooms.get(me.room);
        if (!r) return;
        const kind = msg.kind === 'hand' ? 'hand' : 'chat';
        const out = { type: 'room', kind, from: id, nick: me.nick };
        if (kind === 'chat') out.text = String(msg.text || '').slice(0, 500);
        else out.raised = !!msg.raised;
        for (const pid of r.members) send(clients.get(pid).ws, out);
        break;
      }
      case 'kick': {
        // ホストのみ: 対象を退室させる（stub的だが実際に room から外す）
        if (!me.room) return;
        const r = rooms.get(me.room);
        if (!r || r.host !== id) return;
        const target = clients.get(msg.id);
        if (target && target.room === me.room) {
          send(target.ws, { type: 'kicked' });
          leaveRoom(msg.id);
          broadcastRooms();
        }
        break;
      }
      case 'leave':
        leaveRoom(id);
        broadcastRooms();
        break;
      case 'list':
        send(ws, { type: 'rooms', rooms: roomList() });
        break;
    }
  });

  ws.on('close', () => { leaveRoom(id); clients.delete(id); broadcastRooms(); });
});

server.listen(PORT, () => console.log(`voice-rooms listening on http://localhost:${PORT}`));
