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

export function emoccReply(contextText, { timeoutMs = 60000 } = {}) {
  return new Promise((resolve, reject) => {
    const env = { ...process.env };
    delete env.CLAUDECODE;
    delete env.CLAUDE_CODE_ENTRYPOINT;
    const prompt =
      `${EMOCC_SYSTEM}\n\n--- 直近の会話（古い→新しい）---\n${contextText}\n\n` +
      `上の会話に EmoCC として返す。思考・理由・前置き・メタ説明は一切書かない。\n` +
      `出力は必ず1行で、「REPLY: 」に続けて投稿する本文だけを書くこと。\n` +
      `例: REPLY: おう、待ってるわ`;
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
