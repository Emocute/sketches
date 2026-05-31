import { emoccReply } from '../lib/claude.mjs';
const cases = {
  '荒らし': 'ソラニン: こんにちは〜\n毛の可能性: おちんちん',
  'コマンド的': 'ソラニン: !stop',
  '音楽の話': 'えも: 最近のお気に入りのコード進行ある？\nソラニン: 借用和音すき',
  '話しかけ': 'えも: Emo Claude はどう思う？',
};
for (const [k, ctx] of Object.entries(cases)) {
  const r = await emoccReply(ctx, { timeoutMs: 90000 });
  console.log(`【${k}】 ->`, r === '' ? '[skip=黙る]' : JSON.stringify(r));
}
