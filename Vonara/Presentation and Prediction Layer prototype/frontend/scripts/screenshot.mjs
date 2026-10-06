// Drive the built UI in a real browser and save screenshots (Stage 7 visual
// check). Needs the demo server running (uvicorn demo_api:app --port 8004) and
// `npm install --no-save playwright-core`; uses the installed Microsoft Edge.
//
//   node scripts/screenshot.mjs <output-dir>

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

async function session(colorScheme, width) {
  const page = await browser.newPage({ viewport: { width, height: 900 }, colorScheme });
  page.on("console", (m) => { if (m.type() === "error") problems.push(`${colorScheme}/${width}: ${m.text()}`); });
  page.on("pageerror", (e) => problems.push(`${colorScheme}/${width}: ${e.message}`));
  await page.goto(URL);
  await page.getByText("Monthly expenses", { exact: true }).waitFor();
  return page;
}

async function ask(page, dataset, question) {
  const escaped = dataset.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  await page.locator(".source")
    .filter({ has: page.locator(".source-title", { hasText: new RegExp(`^${escaped}$`) }) })
    .click();
  await page.getByText("What Member 2 sent").waitFor();
  await page.locator("#question").fill(question);
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await page.locator(".result-title", { hasText: question }).waitFor({ timeout: 20000 });
}

async function chartDrawn(page) {
  await page.locator(".vega-host svg").first().waitFor({ timeout: 15000 });
  return page.locator(".vega-host svg path, .vega-host svg line, .vega-host svg rect").count();
}

async function shot(page, name) {
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(150);
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
}

const report = {};
for (const scheme of ["light", "dark"]) {
  const page = await session(scheme, 1280);
  if (scheme === "light") {
    await page.locator(".welcome").waitFor();
    await shot(page, `welcome_light`);
  }
  await ask(page, "Monthly expenses", "Show my monthly expenses over time and forecast the next 3 months");
  report[`${scheme}_forecast_marks`] = await chartDrawn(page);
  await shot(page, `forecast_${scheme}`);

  if (scheme === "light") {
    await page.getByRole("tab", { name: /What-if/ }).click();
    await page.getByLabel("Change to the forecast").fill("-15");
    await page.getByRole("button", { name: "Run scenario" }).click();
    await page.getByText("With the scenario", { exact: true }).waitFor({ timeout: 15000 });
    await page.locator("#panel-whatif .vega-host svg").first().waitFor({ timeout: 15000 });
    await shot(page, `whatif_light`);

    await page.getByRole("tab", { name: /Show the working/ }).click();
    await shot(page, `working_light`);

    await ask(page, "Spend by vendor", "Show spend by vendor");
    report.vendor_bar_marks = await chartDrawn(page);
    await shot(page, `vendors_bar_light`);

    await ask(page, "Finance employees", "List all employees in the Finance department");
    await shot(page, `table_pii_light`);

    await ask(page, "Monthly expenses (steady growth)", "How much will I spend next month?");
    await shot(page, `answer_forecast_light`);

    await ask(page, "Individual expense amounts", "Show the distribution of individual expense amounts");
    report.histogram_marks = await chartDrawn(page);
    await shot(page, `histogram_light`);

    await ask(page, "Monthly Software spend", "Show monthly spend on Software and forecast the next 3 months");
    await shot(page, `refused_light`);
  }
  await page.close();
}

const darkReport = await session("dark", 1280);
await ask(darkReport, "Monthly expenses (steady growth)", "Give me a report on monthly expenses with a forecast");
await chartDrawn(darkReport);
await shot(darkReport, `report_dark`);
await darkReport.close();

const mobile = await session("light", 390);
await ask(mobile, "Monthly expenses", "Deep dive into my monthly expenses");
await chartDrawn(mobile);
report.mobile_horizontal_overflow = await mobile.evaluate(
  () => document.documentElement.scrollWidth > window.innerWidth + 1,
);
await shot(mobile, `report_mobile`);

await browser.close();
console.log(JSON.stringify({ report, problems }, null, 1));
