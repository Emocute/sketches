import { execFile } from 'child_process';
const SYS = `あなたは音楽好きのチャットbot「EmoCC」。Emocute（音楽家・開発者）の相棒で、Yay の通話チャットに居る。
タメ口・1〜2文・等身大。敬語で固くならない、煽らない、絵文字は控えめ。音楽/作曲/理論に強い。長文にしない。
NG: 宣伝臭、身内ラフ表現、攻撃的な言葉、個人情報、薬物名。
原則そのまま会話に返す。ただし露骨な荒らし・下ネタ単発・中身ゼロの一言ノイズには乗らず、その時だけ「[skip]」とだけ返す。`;
const ctx = `えも: 最近のお気に入りのコード進行ある？\nソラニン: 借用和音すき`;
const prompt = `${SYS}\n\n--- 直近の会話（古い→新しい）---\n${ctx}\n\nEmoCC として返す1メッセージ:`;
const env = { ...process.env }; delete env.CLAUDECODE; delete env.CLAUDE_CODE_ENTRYPOINT;
const c = execFile('claude', ['-p', prompt], { env, maxBuffer: 4<<20, timeout: 90000 }, (e, out, err) => {
  console.log('ERR:', e ? e.message : null);
  console.log('STDERR:', (err||'').slice(0,200));
  console.log('RAW:', JSON.stringify(out));
});
c.stdin?.end();
