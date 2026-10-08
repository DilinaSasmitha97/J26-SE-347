// Drive the built UI in a real browser and save screenshots (visual check).
// Needs the demo server running (uvicorn demo_api:app --port 8004) and
// `npm install --no-save playwright-core`; uses the installed Microsoft Edge.
//
//   node scripts/screenshot.mjs <output-dir>        (UI_URL=http://localhost:8005 for another port)

import { chromium } from "playwright-core";
import { existsSync, mkdirSync } from "node:fs";

const OUT = process.argv[2] || "screenshots";
const URL = process.env.UI_URL || "http://localhost:8004";
const EDGE = [
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
].find((p) => existsSync(p));
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ executablePath: EDGE, headless: true });
const problems = [];
const report = { page_scrolls: {} };

async function session(colorScheme, width, height = 900) {
  const context = await browser.newContext({ viewport: { width, height }, colorScheme });
  const page = await context.newPage();
  page.on("console", (m) => { if (m.type() === "error") problems.push(`${colorScheme}/${width}: ${m.text()}`); });
  page.on("pageerror", (e) => problems.push(`${colorScheme}/${width}: ${e.message}`));
  return page;
}

async function open(page, path, waitFor) {
  await page.goto(`${URL}/#${path}`);
  await page.locator(waitFor).first().waitFor({ timeout: 20000 });
  await page.waitForTimeout(300);
}

async function shot(page, name) {
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(150);
  // The layout is meant to fit the window: record whether the page itself scrolls.
  report.page_scrolls[name] = await page.evaluate(
    () => document.documentElement.scrollHeight > window.innerHeight + 1);
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
}

async function ask(page, question) {
  await page.locator("#question").fill(question);
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await page.locator(".result-title", { hasText: question }).waitFor({ timeout: 20000 });
}

async function chartDrawn(page) {
  await page.locator(".vega-host svg").first().waitFor({ timeout: 15000 });
  return page.locator(".vega-host svg path, .vega-host svg line, .vega-host svg rect").count();
}

const overflow = (page) => page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);

for (const scheme of ["light", "dark"]) {
  const page = await session(scheme, 1440);
  await open(page, "/ask/expenses_a", ".chip");
  await shot(page, `ask_${scheme}`);

  await ask(page, "Show my monthly expenses over time and forecast the next 3 months");
  report[`${scheme}_forecast_marks`] = await chartDrawn(page);
  await shot(page, `ask_result_${scheme}`);

  if (scheme === "light") {
    await page.getByRole("tab", { name: /What-if/ }).click();
    await page.getByLabel("Change to the forecast").fill("-15");
    await page.getByRole("button", { name: "Run scenario" }).click();
    await page.getByText("With the scenario", { exact: true }).waitFor({ timeout: 15000 });
    await shot(page, "ask_whatif_light");

    await open(page, "/ask/employees", ".chip");
    await ask(page, "List all employees in the Finance department");
    await open(page, "/ask/software_a", ".chip");
    await ask(page, "Show monthly spend on Software and forecast the next 3 months");
  }

  await open(page, "/admin", "[aria-label='Workspace summary']");
  await shot(page, `dashboard_${scheme}`);

  if (scheme === "light") {
    await open(page, "/admin/sources", "[aria-label='All data sources'] tbody tr");
    await shot(page, "sources_light");
    await open(page, "/admin/sources/employees", "[aria-label='Sample records'] tbody tr");
    await page.locator(".xitem summary").nth(1).click();
    await shot(page, "source_detail_light");
    await open(page, "/admin/configuration", "[aria-label='Forecasting']");
    await shot(page, "configuration_light");
    await open(page, "/admin/activity", "[aria-label='Activity log'] tbody tr");
    await shot(page, "activity_light");
  }
  await page.close();
}

// A common laptop size: everything must still fit without page scrolling.
const laptop = await session("light", 1366, 768);
await open(laptop, "/ask/expenses_d", ".chip");
await ask(laptop, "Give me a report on monthly expenses with a forecast");
await chartDrawn(laptop);
await shot(laptop, "ask_report_1366x768");
await open(laptop, "/admin/sources/employees", "[aria-label='Sample records'] tbody tr");
await shot(laptop, "source_detail_1366x768");
await open(laptop, "/admin/configuration", "[aria-label='Forecasting']");
await shot(laptop, "configuration_1366x768");
await laptop.close();

const mobile = await session("light", 390, 844);
await open(mobile, "/ask/expenses_d", ".chip");
await ask(mobile, "Give me a report on monthly expenses with a forecast");
await chartDrawn(mobile);
report.mobile_ask_overflow = await overflow(mobile);
await shot(mobile, "ask_result_mobile");
await open(mobile, "/admin", "[aria-label='Workspace summary']");
report.mobile_dashboard_overflow = await overflow(mobile);
await shot(mobile, "dashboard_mobile");

await browser.close();
console.log(JSON.stringify({ report, problems }, null, 1));
