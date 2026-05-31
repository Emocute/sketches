import { connectYay, openChatPanel, readMessages } from '../lib/yay.mjs';
const { browser, page } = await connectYay();
console.log('connected:', page.url());
await openChatPanel(page);
const msgs = await readMessages(page);
console.log('messages:', JSON.stringify(msgs, null, 2));
await browser.close();
