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
check(`334 cards rendered (got ${total})`, total === 334);

const visible = () => page.locator('.card:visible').count();
check(`all cards visible at start (${await visible()})`, (await visible()) === 334);

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

// a folded alternate can still be searched from the index (union signature)
await page.goto(`${BASE}/index.html`);
await page.waitForTimeout(100);
await page.fill('#search', 'tourtiere');   // not present; sanity that search still works
await page.fill('#search', 'allspice');    // appears in the meat-pie versions
await page.waitForTimeout(120);
const allspice = await page.locator('.card:visible').count();
check(`ingredient in a folded version is searchable (${allspice} cards)`, allspice > 0);

// --- version switcher on a dish (multi-version) page ---
await page.goto(`${BASE}/recipe/meat-pie.html`);
await page.waitForTimeout(150);
const pills = await page.locator('.ver-pill').count();
check(`meat-pie has 3 version pills (${pills})`, pills === 3);
const visibleVersions = () => page.locator('.version:visible').count();
check(`only one version shown initially (${await visibleVersions()})`, (await visibleVersions()) === 1);
const firstSel = await page.locator('.ver-pill[aria-selected="true"]').textContent();
check(`primary version selected first ("${firstSel.trim()}")`, firstSel.trim() === 'Meat Pie');
// switch to a French Meat Pie version
await page.click('.ver-pill:has-text("French Meat Pie")');
await page.waitForTimeout(120);
check(`still exactly one version after switch (${await visibleVersions()})`, (await visibleVersions()) === 1);
const activeId = await page.locator('.version:visible').getAttribute('id');
check(`switched to a french-meat-pie version (${activeId})`, /french-meat-pie/.test(activeId));

// --- a folded recipe's old URL redirects to the dish page ---
await page.goto(`${BASE}/recipe/french-meat-pie.html`);
await page.waitForTimeout(300);
check(`old alternate URL redirects to dish page (${page.url()})`, /meat-pie\.html/.test(page.url()));
check(`redirect preselects the right version`, /#v-french-meat-pie/.test(page.url()));
const afterRedirect = await page.locator('.version:visible').getAttribute('id');
check(`redirected version is shown (${afterRedirect})`, afterRedirect === 'v-french-meat-pie');

await browser.close();
console.log(`\n${failures === 0 ? 'ALL PASSED' : failures + ' FAILED'}`);
process.exit(failures === 0 ? 0 : 1);
