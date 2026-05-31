import { emoccReply } from '../lib/claude.mjs';
const cases = {
  '雑談(眠い)': 'ソラニン: ねむい〜\n毛の可能性: 今日だるかった',
  '飯': 'えも: 飯何にしようか迷ってる',
  'ゲーム': 'ソラニン: 最近スプラ2ばっかやってる',
  '質問(音楽)': 'えも: EmoCC は転調の話できる？',
  '雑な一言': 'ソラニン: あ〜',
};
for (const [k, ctx] of Object.entries(cases)) {
  const r = await emoccReply(ctx, { timeoutMs: 90000 });
  console.log(`【${k}】`, JSON.stringify(r));
}
