import { emoccReply } from '../lib/claude.mjs';
const cases = [
  'えも: 生きてるか\nソラニン: ちょっとまってね',
  'ソラニン: andymoriのteen’sって曲どう思う？',
  '毛の可能性: おちんちん',
];
for (const ctx of cases) {
  const t = Date.now();
  const r = await emoccReply(ctx, { timeoutMs: 90000 });
  console.log(`(${((Date.now()-t)/1000).toFixed(1)}s)`, JSON.stringify(r));
}
