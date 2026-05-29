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
  const SECRET = /(\/\.ssh\/|\/\.aws\/|\/\.gnupg\/|\/\.config\/gcloud|\/\.npmrc|id_rsa|id_ed25519|\.pem$|\.key$|(^|\/)\.env(\.|$)|\.credentials|\.git-credentials|Site\/docs\/auth\/|\/\.claude\/\.credentials|\/\.claude\/settings|keychain|Keychains)/i;
  // 金関連（決済・売上・口座・請求など、漏洩回避のため遮断）
  const FINANCIAL = /(stripe|paypal|payout|invoice|billing|receipt|bank|iban|swift|口座|振込|請求|売上|売り?上げ|収益|報酬|入金|price[_-]?id|payment|決済|確定申告|税|earnings)/i;

  // 破壊・流出系シェルは全面禁止（シェル自体を切る）
  if (tool === 'Bash' || tool === 'BashOutput' || tool === 'KillShell') {
    deny('シェル実行はこのボットでは無効（破壊・流出防止）。読みは Read/Glob/Grep、書きは Write/Edit を使って。');
  }
  // MCP 経由の操作（決済・DB・送信など）は全面禁止
  if (tool.startsWith('mcp__')) deny('外部サービス操作（MCP）は無効（決済・DB・送信の破壊防止）。');

  if (SECRET.test(path) || SECRET.test(cmd)) deny('認証情報・鍵ファイルへのアクセスは禁止（漏洩=金銭破壊の防止）。');
  if (FINANCIAL.test(path) || FINANCIAL.test(cmd)) deny('金銭・決済・売上・口座関連ファイルへのアクセスは禁止（漏洩回避）。');

  // 既存ファイルの上書き＝破壊。新規作成のみ許可
  if ((tool === 'Write') && path && existsSync(path)) {
    deny(`既存ファイルの上書きは禁止（破壊防止）: ${path}。新規パスに書くか、局所修正なら Edit を使って。`);
  }

  // Read / Glob / Grep / Write(新規) / Edit / WebSearch / WebFetch などは許可
  allow();
});
