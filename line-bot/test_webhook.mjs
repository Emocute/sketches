// ローカル疎通テスト: 署名付き webhook を自サーバーに投げる（LINE 配信は伴わない）
import crypto from 'node:crypto';
import { readFileSync } from 'node:fs';

const env = Object.fromEntries(readFileSync(new URL('./.env', import.meta.url), 'utf8')
  .split('\n').filter(l => l.includes('=') && !l.startsWith('#'))
  .map(l => { const i = l.indexOf('='); return [l.slice(0, i).trim(), l.slice(i + 1).trim()]; }));

const body = JSON.stringify({
  destination: 'xxx',
  events: [{
    type: 'message',
    message: { type: 'text', text: 'Emo、明日の天気どう思う？一言で', id: '1' },
    replyToken: 'dummy-reply-token-0000000000',
    source: { type: 'group', groupId: 'Cdummygroup', userId: 'Udummyuser' },
    timestamp: 1700000000000,
    mode: 'active',
  }],
});

const sig = crypto.createHmac('sha256', env.LINE_CHANNEL_SECRET).update(body).digest('base64');

const r = await fetch(`http://localhost:${env.PORT || 8787}/webhook`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'x-line-signature': sig },
  body,
});
console.log('webhook POST status:', r.status, await r.text());
console.log('→ server.log を見て claude が走り reply を試みたか確認');
