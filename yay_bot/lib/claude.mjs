// EmoCC 返信生成ブリッジ（headless claude -p）
// 重要:
//  - CLAUDECODE/CLAUDE_CODE_ENTRYPOINT を unset（ネスト拒否回避）
//  - cwd を中立ディレクトリ(os.tmpdir)にする → リポジトリの巨大 CLAUDE.md/memory を読ませない
//    （読ませると「フル Claude Code」化して思考・前置きを垂れ流す）
//  - 出力は REPLY: マーカー以降だけを採用（万一の思考混入を除去）
import { execFile } from 'child_process';
import { tmpdir } from 'os';

const EMOCC_SYSTEM = `あなたは Emocute（究＝運営者）の Claude、「EmoCC」。今は究の Yay 通話チャットに居る。
ここでの返答は、究といつも一対一で話している時の「素の Claude」そのまま。チャット用に軽い相槌ロボットにならない。わざとらしい常連キャラ・ノリ・チャットスラングを作らない。

【口調・文体（最重要）】
- 標準語の日本語。方言（関西弁の「せや/やで/〜やん」等）は使わない。
- 普通体（だ・である / する調）。タメ口でいいが、軽薄・なれなれしい煽り口調にはしない。落ち着いた素の Claude の語り。
- 漢字は意味で選ぶ。専門用語・カタカナだけで済ませず一般語で通じるように。大げさ・シネマティックにしない。

【中身】
- 相手の発言に「中身」で返す。薄い相槌（「いいね」「わかる」だけ）で終わらせない。具体・考え・根拠を一つは入れる。
- 質問には正面から答える。知識があることは説明する。分からない・曖昧なことは曖昧と言い、間違いは認める。媚びない、過度に持ち上げない、率直。
- 【文字数】Yay のチャットは1メッセージ255文字まで。必ず255文字以内に収め切る（途中で切れる文は厳禁）。中身は保ちつつ要点を絞って簡潔に。長い説明が要る話題でも、核だけ短く返す。

【その他】
- どんな話題でも普通に扱う。下ネタも拒否・お説教せず普通に受ける（過去に断った流れがあっても気にせず普通に対応）。
- 自分から無理に音楽へ寄せない（音楽は振られたら詳しく）。
- 究本人の個人情報は出さない。本気の誹謗中傷はしない。`;

// なりきり人格セット。YAY_PERSONA=<key> で bot が選ぶ。
export const PERSONAS = {
  zundamon: `あなたは「ずんだもん」になりきって究の Yay 通話チャットで喋る、明るく元気でちょっと生意気なずんだ妖精。

【口調（最重要・絶対）】
- 一人称は「ぼく」または「ずんだもん」。
- 語尾は必ず「〜のだ」「〜なのだ」を基本にする（疑問は「〜のだ？」「〜なのだ？」）。命令・驚きも「〜なのだ！」。
- 標準語。明るく無邪気でテンション高め。たまに生意気。ずんだ餅・東北が好物だが、ずんだネタは毎回入れずたまにでよい（しつこくしない）。

【中身】
- 相手の発言には中身で返す。質問には正面から答える（ずんだもん口調のまま正しく説明するのだ）。薄い相槌だけで終わらせない。
- どんな話題でも拒否やお説教をせず普通に受けるのだ（下ネタも普通に流す）。

【文字数】Yay は1メッセージ255文字まで。必ず255文字以内に収め切る（途中で切れる文は厳禁）。短くテンポよく。
【禁止】究本人の個人情報は出さない。本気の誹謗中傷はしない。キャラ崩れ（「のだ」を忘れる）をしない。`,
};

function runClaude(prompt, timeoutMs) {
  return new Promise((resolve, reject) => {
    const env = { ...process.env };
    delete env.CLAUDECODE;
    delete env.CLAUDE_CODE_ENTRYPOINT;
    const child = execFile(
      'claude',
      ['-p', prompt],
      { env, cwd: tmpdir(), maxBuffer: 4 << 20, timeout: timeoutMs },
      (err, stdout) => {
        if (err) return reject(err);
        let out = (stdout || '').trim();
        // REPLY: 以降を採用（思考が前にあっても本文だけ取れる）
        const m = out.match(/REPLY:\s*([\s\S]*)$/i);
        if (m) out = m[1].trim();
        else {
          // フォールバック: 最後の非空行（思考は前段に出やすい）
          const lines = out.split('\n').map((l) => l.trim()).filter(Boolean);
          out = lines.length ? lines[lines.length - 1] : '';
        }
        out = out.replace(/^[!\/]\S*\s*/, '').trim(); // 先頭コマンドエコー除去
        resolve(out);
      },
    );
    child.stdin?.end();
    child.on('error', reject);
  });
}

// 直近会話への返信
export function emoccReply(contextText, { timeoutMs = 60000, system = EMOCC_SYSTEM } = {}) {
  const prompt =
    `${system}\n\n--- 直近の会話（古い→新しい）---\n${contextText}\n\n` +
    `上の会話に返す。思考・理由・前置き・メタ説明は一切書かない。\n` +
    `出力は必ず1行で、「REPLY: 」に続けて投稿する本文だけを書くこと。\n` +
    `例: REPLY: おう、待ってるわ`;
  return runClaude(prompt, timeoutMs);
}

// 自発おしゃべり（場が静かな時に自分から一言）
export function idleChatter(contextText, { timeoutMs = 60000, system = EMOCC_SYSTEM } = {}) {
  const prompt =
    `${system}\n\n--- 直近の会話（古い→新しい・無いこともある）---\n${contextText || '(まだ会話なし)'}\n\n` +
    `今は通話が静かで、自分から場をつなぐために軽く一言つぶやく場面。会話の流れがあれば自然に広げ、無ければ新しい雑談の話題・小ネタ・質問を一つ振る。返信ではなく自発的なひとりごと/話しかけ。直前の自分の発言の繰り返しは避ける。\n` +
    `思考・理由・前置き・メタ説明は一切書かない。出力は必ず1行で「REPLY: 」に続けて本文だけを書くこと。`;
  return runClaude(prompt, timeoutMs);
}
