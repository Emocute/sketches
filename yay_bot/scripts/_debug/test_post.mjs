import { connectYay, openChatPanel, postMessage } from '../lib/yay.mjs';
const { browser, page } = await connectYay();
await openChatPanel(page);
await postMessage(page, process.argv[2] || 'つながった、よろしく〜');
await page.waitForTimeout(800);
await page.screenshot({ path: 'assets/_post_check.png' });
console.log('posted + screenshot assets/_post_check.png');
await browser.close();
