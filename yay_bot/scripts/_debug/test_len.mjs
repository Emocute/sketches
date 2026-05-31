import { emoccReply } from '../lib/claude.mjs';
for (const ctx of ['えも: 平均律と純正律の違いって結局なに？', '夏: 最近寝つき悪くてさ', 'ソラニン: ちんちんってなに']) {
  const r = await emoccReply(ctx, { timeoutMs: 90000 });
  console.log(`[${r.length}字] ${r}`);
}
