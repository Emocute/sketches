// Claude ロゴ(simpleicons ベクター)から高解像度アバターを生成
// 出力: assets/claude_hi_{color,wonb,bonw}.svg + .png(2048)
import { readFileSync, writeFileSync } from 'fs';
import { execSync } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __dir = path.dirname(fileURLToPath(import.meta.url));
const ASSETS = path.join(__dir, '..', 'assets');
const SI = '/tmp/si_claude.svg';
const SIZE = 2048;

const d = readFileSync(SI, 'utf8').match(/d="([^"]+)"/)[1];

// burst を 24x24  viewBox 内で 0.7 倍に縮小して中央寄せ（余白確保）
const burst = (fill) =>
  `<g transform="translate(3.6,3.6) scale(0.7)"><path d="${d}" fill="${fill}"/></g>`;

const make = (name, bg, fg, rounded = true) => {
  const rx = rounded ? 4.2 : 0;
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">` +
    `<rect width="24" height="24" rx="${rx}" ry="${rx}" fill="${bg}"/>` +
    burst(fg) +
    `</svg>`;
  const svgPath = path.join(ASSETS, `claude_hi_${name}.svg`);
  const pngPath = path.join(ASSETS, `claude_hi_${name}.png`);
  writeFileSync(svgPath, svg);
  execSync(`magick -background none -density 600 "${svgPath}" -resize ${SIZE}x${SIZE} "${pngPath}"`);
  console.log(`made ${name}: ${pngPath}`);
};

make('color', '#D97757', '#FFFFFF'); // 普通版（テラコッタ + 白burst）
make('wonb', '#000000', '#FFFFFF');  // 白黒: 白burst on 黒
make('bonw', '#FFFFFF', '#000000');  // 白黒: 黒burst on 白
