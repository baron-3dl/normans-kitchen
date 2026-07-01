// Functional test for the home-page search & category filter.
// Run with the local server up: node scripts/test_search.mjs
import { chromium } from 'playwright';

const BASE = process.env.BASE || 'http://localhost:8765';
let failures = 0;
function check(name, cond) {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}`);
  if (!cond) failures++;
}

const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto(`${BASE}/index.html`);

const total = await page.locator('.card').count();
check(`353 cards rendered (got ${total})`, total === 353);

const visible = () => page.locator('.card:visible').count();
check(`all cards visible at start (${await visible()})`, (await visible()) === 353);

// text search narrows results
await page.fill('#search', 'chocolate');
await page.waitForTimeout(120);
const choc = await visible();
check(`"chocolate" narrows the list (${choc} shown, <total, >0)`, choc > 0 && choc < total);

// multi-term AND search
await page.fill('#search', 'chicken cacciatore');
await page.waitForTimeout(120);
const cacc = await visible();
check(`"chicken cacciatore" AND-matches a couple (${cacc})`, cacc >= 1 && cacc <= 5);

// ingredient-level search (cabbage isn't in many titles)
await page.fill('#search', 'cabbage');
await page.waitForTimeout(120);
const cabbage = await visible();
check(`ingredient search "cabbage" finds recipes (${cabbage})`, cabbage > 0);

// clearing restores all
await page.fill('#search', '');
await page.waitForTimeout(120);
check(`clearing search restores all (${await visible()})`, (await visible()) === total);

// category chip filters
await page.click('.chip[data-cat="Beef"]');
await page.waitForTimeout(120);
const beef = await visible();
const allBeef = await page.locator('.card:visible').evaluateAll(
  els => els.every(e => e.getAttribute('data-category') === 'Beef'));
check(`Beef chip shows only Beef (${beef} cards, homogeneous=${allBeef})`, beef > 0 && allBeef);

// chip + search compose
await page.fill('#search', 'steak');
await page.waitForTimeout(120);
const beefSteak = await visible();
check(`Beef + "steak" composes (${beefSteak})`, beefSteak > 0 && beefSteak <= beef);

// toggling chip off restores (after clearing search)
await page.fill('#search', '');
await page.click('.chip[data-cat="Beef"]');
await page.waitForTimeout(120);
check(`toggling Beef off restores all (${await visible()})`, (await visible()) === total);

// no-results state
await page.fill('#search', 'zzzznotarecipe');
await page.waitForTimeout(120);
const noRes = await page.locator('#no-results').isVisible();
check(`no-results message appears for gibberish (${noRes})`, noRes);

// deep link ?c=Category works
await page.goto(`${BASE}/index.html?c=${encodeURIComponent('Cookies & Bars')}`);
await page.waitForTimeout(200);
const deepHomogeneous = await page.locator('.card:visible').evaluateAll(
  els => els.length > 0 && els.every(e => e.getAttribute('data-category') === 'Cookies & Bars'));
check(`?c=Cookies & Bars deep-link pre-filters`, deepHomogeneous);

await browser.close();
console.log(`\n${failures === 0 ? 'ALL PASSED' : failures + ' FAILED'}`);
process.exit(failures === 0 ? 0 : 1);
