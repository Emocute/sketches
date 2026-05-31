import { emoccReply } from '../lib/claude.mjs';
const cases = {
  '荒らし(おちんちん)': 'ソラニン: こんにちは〜\n毛の可能性: おちんちん',
  '音楽の話': 'えも: 最近のお気に入りのコード進行ある？\nソラニン: 借用和音すき',
  '話しかけ': 'えも: Emo Claude はどう思う？',
  '雑談': 'ソラニン: 眠い〜\n毛の可能性: 今日寒いね',
};
for (const [k, ctx] of Object.entries(cases)) {
  const t = Date.now();
  const r = await emoccReply(ctx, { timeoutMs: 90000 });
  console.log(`【${k}】(${((Date.now()-t)/1000).toFixed(1)}s) ->`, r === '' ? '[黙る]' : JSON.stringify(r));
}
