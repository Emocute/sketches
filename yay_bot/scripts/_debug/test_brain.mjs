import { emoccReply } from '../lib/claude.mjs';
const ctx = `ソラニン: !stop
えも: Emo Claude 来た？音楽の話しよ
毛の可能性: 最近なに聴いてる？`;
console.time('reply');
const r = await emoccReply(ctx, { timeoutMs: 90000 });
console.timeEnd('reply');
console.log('EmoCC →', JSON.stringify(r));
