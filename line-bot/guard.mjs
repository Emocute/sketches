#!/usr/bin/env node
// PreToolUse ガード: 「読みは広く・新規書き込みは可・破壊と漏洩は不可」を強制する。
// claude が Read/Write/Edit/Bash 等を使う直前に呼ばれ、stdin の JSON で許否を返す。
import { existsSync } from 'node:fs';

const deny = (reason) => {
  process.stdout.write(JSON.stringify({
    hookSpecificOutput: { hookEventName: 'PreToolUse', permissionDecision: 'deny', permissionDecisionReason: reason },
  }));
  process.exit(0);
};
const allow = () => {
  process.stdout.write(JSON.stringify({
    hookSpecificOutput: { hookEventName: 'PreToolUse', permissionDecision: 'allow', permissionDecisionReason: 'ok' },
  }));
  process.exit(0);
};

let input = '';
process.stdin.on('data', (c) => (input += c));
process.stdin.on('end', () => {
  let data = {};
  try { data = JSON.parse(input || '{}'); } catch {}
  const tool = data.tool_name || '';
  const ti = data.tool_input || {};
  const path = String(ti.file_path || ti.path || ti.notebook_path || '');
  const cmd = String(ti.command || '');

  // 認証情報・鍵・個人セキュリティ領域（読み書き問わず全面拒否）
  const SECRET = /(\/\.ssh\/|\/\.aws\/|\/\.gnupg\/|\/\.config\/gcloud|\/\.npmrc|id_rsa|id_ed25519|\.pem(\b|$)|\.key(\b|$)|(^|[\/\s'"])\.env(\b|\.|$)|\.credentials|\.git-credentials|Site\/docs\/auth\/|\/\.claude\/\.credentials|\/\.claude\/settings|keychain|Keychains)/i;
  // 金関連（決済・売上・口座・請求など、漏洩回避のため遮断）
  const FINANCIAL = /(stripe|paypal|payout|invoice|billing|receipt|bank|iban|swift|口座|振込|請求|売上|売り?上げ|収益|報酬|入金|price[_-]?id|payment|決済|確定申告|税|earnings)/i;

  // プロセス kill は禁止のまま（稼働中プロセスの破壊防止）
  if (tool === 'KillShell') deny('プロセス kill は無効。');
  // MCP 経由の操作（決済・DB・送信など）は全面禁止
  if (tool.startsWith('mcp__')) deny('外部サービス操作（MCP）は無効（決済・DB・送信の破壊防止）。');

  // Bash は解禁。ただし破壊・kill・課金・外部送信に当たるコマンドは拒否（資産削除禁止＋漏洩防止）
  if (tool === 'Bash' || tool === 'BashOutput') {
    // 削除・強制リセット・kill・権限再帰変更・fork bomb 等
    const DESTRUCTIVE = /(^|[;&|]\s*|\s)(rm|rmdir|unlink|shred|trash|truncate)\s+|(-delete|--delete)\b|\bmv\b[^|;]*\.Trash|\bdd\b\s|\bmkfs|\bkill\b|\bkillall\b|\bpkill\b|\bgit\s+(push|reset\s+--hard|clean|rebase)\b|\bchmod\s+-R\b|\bchown\s+-R\b|:\s*\(\s*\)\s*\{/i;
    // 外部へのデータ送信（POST/アップロード/コピー）
    const EXFIL = /\b(curl|wget)\b[^|;]*(\s-d\b|--data|\s-F\b|--form|\s-T\b|--upload-file|-X\s*POST|-X\s*PUT)|\bscp\b|\bnc\b\s|\brsync\b[^|;]*::/i;
    if (DESTRUCTIVE.test(cmd)) deny('破壊的シェル操作（削除/kill/強制リセット等）は禁止。資産削除は不可。');
    if (EXFIL.test(cmd)) deny('外部へのデータ送信（POST/アップロード等）は禁止（漏洩防止）。');
    // この下の SECRET / FINANCIAL チェックで cmd も検閲され、認証・金関連の読み出しは塞がれる
  }

  if (SECRET.test(path) || SECRET.test(cmd)) deny('認証情報・鍵ファイルへのアクセスは禁止（漏洩=金銭破壊の防止）。');
  if (FINANCIAL.test(path) || FINANCIAL.test(cmd)) deny('金銭・決済・売上・口座関連ファイルへのアクセスは禁止（漏洩回避）。');

  // 既存ファイルの上書き＝破壊。新規作成のみ許可
  if ((tool === 'Write') && path && existsSync(path)) {
    deny(`既存ファイルの上書きは禁止（破壊防止）: ${path}。新規パスに書くか、局所修正なら Edit を使って。`);
  }

  // Read / Glob / Grep / Write(新規) / Edit / WebSearch / WebFetch などは許可
  allow();
});
