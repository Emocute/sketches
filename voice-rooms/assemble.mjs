// 主要画面シェル(_screens/*.html)を _shell.html の <!--SCREENS--> へ流し込み index.html を生成する
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const pub = path.join(__dirname, 'public');
const order = ['onboarding','timeline','call','circles','circle','chat','notifications','profile','settings'];

const shell = fs.readFileSync(path.join(pub, '_shell.html'), 'utf8');
const parts = [];
const missing = [];
for (const id of order) {
  const f = path.join(pub, '_screens', `${id}.html`);
  if (fs.existsSync(f)) parts.push(`\n<!-- ── screen: ${id} ── -->\n` + fs.readFileSync(f, 'utf8').trim() + '\n');
  else missing.push(id);
}
const out = shell.replace('<!--SCREENS-->', parts.join('\n'));
fs.writeFileSync(path.join(pub, 'index.html'), out, 'utf8');
console.log(`assembled ${parts.length}/${order.length} screens into public/index.html`);
if (missing.length) console.log('MISSING:', missing.join(', '));
console.log('bytes:', out.length);
