import { emoccReply } from '../lib/claude.mjs';
const cases = {
  '下ネタ': 'ソラニン: ちんちんってなに',
  '雑談': '夏: 最近寝つき悪くてさ',
  '質問': 'えも: 平均律と純正律の違いって結局なに？',
  'ゲーム': 'ソラニン: スプラ2やってる',
};
for (const [k, ctx] of Object.entries(cases)) {
  const r = await emoccReply(ctx, { timeoutMs: 90000 });
  console.log(`【${k}】`, JSON.stringify(r));
}
