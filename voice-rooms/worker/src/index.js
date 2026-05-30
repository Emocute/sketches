// voice-rooms — Cloudflare Worker + Durable Object 版（24時間・スリープ無し）
// Worker: 鍵ゲート / /ice / 静的配信 / WS を Hub DO へ。
// Hub(Durable Object): 全ルーム＋全接続を1インスタンスで捌く（旧 Node server.js のロジック移植）。

import { DurableObject } from 'cloudflare:workers';

async function sha256hex(s) {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, '0')).join('');
}
function cookie(req, name) {
  const m = (req.headers.get('cookie') || '').match(new RegExp('(?:^|;\\s*)' + name + '=([a-f0-9]+)'));
  return m ? m[1] : '';
}
const LOGIN_PAGE = (err) => `<!doctype html><html lang="ja"><meta charset="utf8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>voice rooms</title><body style="margin:0;height:100vh;display:flex;align-items:center;justify-content:center;background:#0a0a0a;color:#ececec;font-family:-apple-system,'Helvetica Neue',sans-serif"><form method="POST" action="/gate" style="width:280px;text-align:center"><div style="font-weight:600;font-size:18px;letter-spacing:.02em;margin-bottom:20px">voice rooms</div><input name="p" type="password" placeholder="鍵" autofocus autocomplete="current-password" style="width:100%;box-sizing:border-box;background:#0e0e0e;border:1px solid #242424;color:#ececec;border-radius:20px;padding:11px 14px;font-size:15px;outline:none"><button style="width:100%;margin-top:12px;background:#ff5e7e;color:#160a0c;font-weight:700;border:0;border-radius:22px;padding:12px;font-size:14px;cursor:pointer">入る</button>${err ? '<div style="color:#ff5e7e;font-size:12px;margin-top:10px">鍵が違う</div>' : ''}</form></body></html>`;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const pass = env.GATE_PASS || '';
    const token = pass ? await sha256hex('vr|' + pass) : '';
    const isWS = (request.headers.get('Upgrade') || '').toLowerCase() === 'websocket';

    if (pass) {
      if (request.method === 'POST' && url.pathname === '/gate') {
        const form = await request.formData();
        if ((form.get('p') || '') === pass) {
          return new Response(null, { status: 302, headers: {
            'Set-Cookie': `vr_gate=${token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000; Secure`,
            'Location': '/',
          }});
        }
        return new Response(LOGIN_PAGE(true), { status: 401, headers: { 'Content-Type': 'text/html; charset=utf-8' } });
      }
      if (cookie(request, 'vr_gate') !== token) {
        if (isWS) return new Response('unauthorized', { status: 401 });
        return new Response(LOGIN_PAGE(false), { status: 200, headers: { 'Content-Type': 'text/html; charset=utf-8' } });
      }
    }

    if (url.pathname === '/ice') {
      const list = [{ urls: 'stun:stun.l.google.com:19302' }];
      if (env.TURN_URLS) list.push({
        urls: env.TURN_URLS.split(',').map((s) => s.trim()).filter(Boolean),
        username: env.TURN_USERNAME || '', credential: env.TURN_CREDENTIAL || '',
      });
      return Response.json({ iceServers: list }, { headers: { 'Cache-Control': 'no-store' } });
    }

    if (isWS) {
      const id = env.HUB.idFromName('global');
      return env.HUB.get(id).fetch(request);
    }
    return env.ASSETS.fetch(request);
  },
};

export class Hub extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    this.clients = new Map(); // id -> { ws, room, nick, tags }
    this.rooms = new Map();   // name -> { members:Set<id>, tags:[], host:id }
    this.nextId = 1;
  }

  send(ws, obj) { try { if (ws.readyState === 1) ws.send(JSON.stringify(obj)); } catch {} }
  roomList() { return [...this.rooms.entries()].map(([name, r]) => ({ name, count: r.members.size, tags: r.tags })); }
  broadcastRooms() { for (const c of this.clients.values()) this.send(c.ws, { type: 'rooms', rooms: this.roomList() }); }

  leaveRoom(id) {
    const me = this.clients.get(id);
    if (!me || !me.room) return;
    const r = this.rooms.get(me.room);
    if (r) {
      r.members.delete(id);
      for (const pid of r.members) this.send(this.clients.get(pid).ws, { type: 'peer-left', id });
      if (r.members.size === 0) this.rooms.delete(me.room);
      else if (r.host === id) { r.host = r.members.values().next().value;
        for (const pid of r.members) this.send(this.clients.get(pid).ws, { type: 'host', id: r.host }); }
    }
    me.room = null;
  }

  async fetch(request) {
    const pair = new WebSocketPair();
    const client = pair[0], server = pair[1];
    server.accept();
    const id = String(this.nextId++);
    this.clients.set(id, { ws: server, room: null, nick: null, tags: [] });
    this.send(server, { type: 'welcome', id, rooms: this.roomList() });

    server.addEventListener('message', (ev) => this.onMessage(id, ev.data));
    const gone = () => { this.leaveRoom(id); this.clients.delete(id); this.broadcastRooms(); };
    server.addEventListener('close', gone);
    server.addEventListener('error', gone);

    return new Response(null, { status: 101, webSocket: client });
  }

  onMessage(id, raw) {
    let msg; try { msg = JSON.parse(raw); } catch { return; }
    const me = this.clients.get(id);
    if (!me) return;
    switch (msg.type) {
      case 'join': {
        this.leaveRoom(id);
        const room = String(msg.room || '').slice(0, 40).trim();
        if (!room) return;
        me.room = room;
        me.nick = String(msg.nick || '').slice(0, 24);
        me.tags = Array.isArray(msg.tags) ? msg.tags.slice(0, 6).map((t) => String(t).slice(0, 16)) : [];
        let r = this.rooms.get(room);
        if (!r) { r = { members: new Set(), tags: me.tags.slice(0, 4), host: id }; this.rooms.set(room, r); }
        const peers = [...r.members].map((pid) => ({ id: pid, nick: this.clients.get(pid).nick }));
        this.send(me.ws, { type: 'peers', peers, host: r.host });
        for (const pid of r.members) this.send(this.clients.get(pid).ws, { type: 'peer-joined', id, nick: me.nick });
        r.members.add(id);
        this.broadcastRooms();
        break;
      }
      case 'signal': {
        const t = this.clients.get(msg.to);
        if (t) this.send(t.ws, { type: 'signal', from: id, data: msg.data });
        break;
      }
      case 'room': {
        if (!me.room) return;
        const r = this.rooms.get(me.room);
        if (!r) return;
        const kind = msg.kind === 'hand' ? 'hand' : 'chat';
        const out = { type: 'room', kind, from: id, nick: me.nick };
        if (kind === 'chat') out.text = String(msg.text || '').slice(0, 500);
        else out.raised = !!msg.raised;
        for (const pid of r.members) this.send(this.clients.get(pid).ws, out);
        break;
      }
      case 'kick': {
        if (!me.room) return;
        const r = this.rooms.get(me.room);
        if (!r || r.host !== id) return;
        const target = this.clients.get(msg.id);
        if (target && target.room === me.room) {
          this.send(target.ws, { type: 'kicked' });
          this.leaveRoom(msg.id);
          this.broadcastRooms();
        }
        break;
      }
      case 'leave': this.leaveRoom(id); this.broadcastRooms(); break;
      case 'list': this.send(me.ws, { type: 'rooms', rooms: this.roomList() }); break;
    }
  }
}
