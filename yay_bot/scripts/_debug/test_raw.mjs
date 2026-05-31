import { execFile } from 'child_process';
const env = { ...process.env };
delete env.CLAUDECODE; delete env.CLAUDE_CODE_ENTRYPOINT;
const prompt = `あなたは音楽好きのチャットbot「EmoCC」。タメ口で1〜2文。
直近の会話:
えも: Emo Claude はどう思う？最近のお気に入りのコード進行ある？
EmoCCとして返す1メッセージ:`;
execFile('claude', ['-p', prompt], { env, maxBuffer: 4<<20, timeout: 90000 }, (e, out, err) => {
  console.log('ERR:', e ? e.message : null);
  console.log('STDERR:', (err||'').slice(0,300));
  console.log('RAW STDOUT:', JSON.stringify(out));
});
