// UI tests over REAL API responses (src/__fixtures__, captured by
// scripts/make_fixtures.py from /api/v4/present and /simulate). Vega needs a
// browser canvas, so charts use a recording stand-in for vega-embed; the spec
// it receives is checked instead.

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App.jsx";
import ResponseView from "./components/ResponseView.jsx";
import { sliderScenario } from "./components/panels.jsx";
import { compact } from "./format.js";
import { PALETTE, chartTitle, themeSpec } from "./theme.js";

import answer from "./__fixtures__/answer.json";
import chartForecast from "./__fixtures__/chart_forecast.json";
import datasets from "./__fixtures__/datasets.json";
import forecastAnswer from "./__fixtures__/forecast_answer.json";
import forecastRefused from "./__fixtures__/forecast_refused.json";
import report from "./__fixtures__/report.json";
import tablePii from "./__fixtures__/table_pii.json";
import whatif from "./__fixtures__/whatif.json";
import whatifRefused from "./__fixtures__/whatif_refused.json";

afterEach(cleanup);

function recorder() {
  const calls = [];
  const embed = vi.fn((el, spec) => {
    calls.push(spec);
    el.setAttribute("data-rendered", spec.mark?.type || "layered");
    return Promise.resolve({ view: { finalize() {} } });
  });
  return { embed, calls };
}

const BACKEND_COLOURS = ["#4C78A8", "#F58518", "#D62728", "#54A24B", "#B279A2"];

const claim = (env, id) => env.summary.claims.find((c) => c.claim_id === id);

describe("response blocks", () => {
  it("shows a single answer as one large figure", () => {
    render(<ResponseView envelope={answer} question="total travel spend" />);
    const card = screen.getByLabelText("Answer");
    expect(within(card).getByText(answer.response.answer.display_value)).toBeInTheDocument();
    expect(screen.getByText("Single answer")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "total travel spend" })).toBeInTheDocument();
    // A single figure is its own key figure: no stat tiles repeat it.
    expect(screen.queryByLabelText("Key figures")).toBeNull();
  });

  it("answers a future single value with the forecast and its range", () => {
    render(<ResponseView envelope={forecastAnswer} />);
    const card = screen.getByLabelText("Answer");
    expect(within(card).getByText("Forecast")).toBeInTheDocument();
    expect(within(card).getByText(/range:/)).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(/Forecast shown/);
  });

  it("shows masked values as Member 2 sent them, and marks masked columns", () => {
    render(<ResponseView envelope={tablePii} />);
    const table = screen.getByLabelText("Table");
    const masked = tablePii.input.masked_columns;
    expect(Object.keys(masked)).toEqual(expect.arrayContaining(["full_name", "email"]));
    for (const row of tablePii.response.table.rows) {
      expect(within(table).getByText(row.email)).toBeInTheDocument();
      expect(row.email).toContain("*");
    }
    expect(within(table).getAllByTitle(/Masked by Member 2/).length).toBe(2);
    expect(within(table).getByText("2 masked columns")).toBeInTheDocument();
    // A record list gets no key figures (totals of salaries are not the point).
    expect(screen.queryByLabelText("Key figures")).toBeNull();
  });

  it("draws the forecast chart with the validated palette, a key, and a table view", async () => {
    const { embed, calls } = recorder();
    render(<ResponseView envelope={chartForecast} embed={embed} />);
    await waitFor(() => expect(embed).toHaveBeenCalled());
    const json = JSON.stringify(calls[0]).toLowerCase();
    for (const c of BACKEND_COLOURS) expect(json).not.toContain(c.toLowerCase());
    expect(json).toContain(PALETTE.light.forecast);
    const key = screen.getByLabelText("Chart key");
    expect(within(key).getByText("Forecast")).toBeInTheDocument();
    expect(within(key).getByText("Forecast range")).toBeInTheDocument();
    expect(within(key).getByText("Past anomaly")).toBeInTheDocument();
    // A seasonal series' normal range is a deviation, not a level: no rules
    // are drawn on the value axis (Stage 7 fix in visualization.py).
    expect(within(key).queryByText("Normal range")).toBeNull();
    // The key replaces Vega's own legend for a single series with overlays.
    expect(calls[0].config.legend.disable).toBe(true);
    for (const layer of calls[0].layer) {
      for (const channel of Object.values(layer.encoding || {})) {
        if (channel && "legend" in channel) expect(channel.legend).toBeNull();
      }
    }
    const anomalyLayer = calls[0].layer.find((l) => l.encoding && l.encoding.shape);
    expect(anomalyLayer.encoding.shape.scale.range).toEqual(["triangle-up", "diamond"]);
    // Markers carry a surface ring; the card header names the chart instead
    // of the backend's title-cased question.
    expect(anomalyLayer.mark.stroke).toBe(PALETTE.light.surface);
    expect(calls[0].title).toBeUndefined();
    expect(screen.getByRole("heading", { name: "Total amount by month" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Table" }));
    expect(screen.getByLabelText(/Chart:/).querySelectorAll("tbody tr").length).toBeGreaterThan(10);
    expect(screen.getByRole("status")).toHaveTextContent(/Forecast shown/);
  });

  it("takes the key figures from the summary's claims, not from the browser", () => {
    render(<ResponseView envelope={chartForecast} embed={recorder().embed} />);
    const tiles = screen.getByLabelText("Key figures");
    expect(within(tiles).getByText(compact(claim(chartForecast, "H1").value))).toBeInTheDocument();
    expect(within(tiles).getByText(compact(claim(chartForecast, "F2.1").value))).toBeInTheDocument();
    expect(within(tiles).getByText(compact(claim(chartForecast, "F3").value))).toBeInTheDocument();
    expect(within(tiles).getByText("Jan 2026")).toBeInTheDocument();
    expect(within(tiles).getByText(/typical error 8\.5%/)).toBeInTheDocument();
  });

  it("says why a requested forecast was refused, and offers no what-if", () => {
    render(<ResponseView envelope={forecastRefused} embed={recorder().embed} onSimulate={vi.fn()} />);
    const notice = screen.getByRole("status");
    expect(notice).toHaveTextContent("Forecast not shown");
    expect(notice).toHaveTextContent(forecastRefused.response.forecast_notice.message.slice(0, 30));
    expect(screen.getByRole("tab", { name: /What-if/ })).toBeDisabled();
  });

  it("lays out a report in the emitted block order with the claim trace", () => {
    render(<ResponseView envelope={report} embed={recorder().embed} />);
    const order = ["Summary", "Table", /Chart:/].map((l) => screen.getByLabelText(l));
    for (let i = 1; i < order.length; i++) {
      expect(order[i - 1].compareDocumentPosition(order[i]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    }
    const working = screen.getByRole("tab", { name: /Show the working/ });
    expect(working).toHaveTextContent(String(report.summary.claims.length));
    fireEvent.click(working);
    expect(screen.getByRole("tabpanel")).toHaveTextContent(claim(report, "H1").text);
  });

  it("lists the anomalies the backend found", () => {
    render(<ResponseView envelope={chartForecast} embed={recorder().embed} />);
    const past = chartForecast.prediction.stage_5_anomaly.historical_anomalies;
    expect(screen.getByRole("tab", { name: /Anomalies/ })).toHaveAttribute("aria-selected", "true");
    const panel = screen.getByLabelText("Anomalies");
    expect(panel.querySelectorAll("li").length).toBe(past.length);
    // A seasonal series is screened against its season, and says so.
    expect(within(panel).getByText(/Apr 2024 · above its seasonal norm/)).toBeInTheDocument();
  });
});

describe("what-if", () => {
  it("shows the simulated change and the scenario chart", async () => {
    const onSimulate = vi.fn(() => Promise.resolve(whatif));
    render(<ResponseView envelope={chartForecast} onSimulate={onSimulate} embed={recorder().embed} />);
    fireEvent.click(screen.getByRole("tab", { name: /What-if/ }));
    fireEvent.click(screen.getByText("cut spending by 10%"));
    await waitFor(() => expect(screen.getByText("With the scenario")).toBeInTheDocument());
    expect(onSimulate).toHaveBeenCalledWith("cut spending by 10%");
    expect(screen.getAllByText(whatif.scenario.spec.parse_note, { exact: false }).length).toBeGreaterThan(0);
  });

  it("turns the slider into words the scenario parser reads", async () => {
    expect(sliderScenario(-15, false)).toBe("reduce by 15%");
    expect(sliderScenario(20, true)).toBe("gradually increase by 20%");
    const onSimulate = vi.fn(() => Promise.resolve(whatif));
    render(<ResponseView envelope={chartForecast} onSimulate={onSimulate} embed={recorder().embed} />);
    fireEvent.click(screen.getByRole("tab", { name: /What-if/ }));
    fireEvent.change(screen.getByLabelText("Change to the forecast"), { target: { value: "-15" } });
    fireEvent.click(screen.getByLabelText("Phase in gradually"));
    fireEvent.click(screen.getByText("Run scenario"));
    await waitFor(() => expect(onSimulate).toHaveBeenCalledWith("gradually reduce by 15%"));
  });

  it("says why a scenario was not simulated", async () => {
    const onSimulate = vi.fn(() => Promise.resolve(whatifRefused));
    render(<ResponseView envelope={chartForecast} onSimulate={onSimulate} embed={recorder().embed} />);
    fireEvent.click(screen.getByRole("tab", { name: /What-if/ }));
    fireEvent.change(screen.getByLabelText("Scenario"), { target: { value: "what if prices change somehow" } });
    fireEvent.click(screen.getByText("Simulate"));
    await waitFor(() => expect(screen.getByText("Scenario not simulated")).toBeInTheDocument());
  });
});

describe("theme", () => {
  it("maps every backend colour to the palette of the active mode", () => {
    const spec = chartForecast.visualization;
    const dark = JSON.stringify(themeSpec(spec, "dark")).toLowerCase();
    expect(dark).toContain(PALETTE.dark.history);
    expect(dark).toContain(PALETTE.dark.surface);
    for (const c of BACKEND_COLOURS) expect(dark).not.toContain(c.toLowerCase());
  });

  it("names charts from the encoding the backend chose", () => {
    expect(chartTitle({ chart_type: "line", x_field: "month", y_field: "total_amount" })).toBe("Total amount by month");
    expect(chartTitle({ chart_type: "histogram", x_field: "amount" })).toBe("Distribution of amount");
    expect(chartTitle({ chart_type: "scatter", x_field: "units_sold", y_field: "revenue" })).toBe("Revenue vs units sold");
  });
});

describe("app", () => {
  it("fetches Member 2's rows, calls the real present endpoint and renders the answer", async () => {
    const rows = { member2_result: { rowCount: 1, truncated: false, columns: [{ name: "total_travel" }],
      masking: { columns: [] } }, security_context: { tenant_id: "tenant_a" }, schema_meta: "", sql: "SELECT 1" };
    const status = { status: "UP", pipeline_version: "1.0", llm_available: false, llm_provider: "none" };
    const fetchMock = vi.fn((url) => {
      const body = { "/demo/datasets": datasets, "/demo/rows": rows, "/api/v4/health": status }[url] || answer;
      return Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    expect(await screen.findByText("API online")).toBeInTheDocument();
    // Sources arrive grouped, each with its kind.
    expect(screen.getByText("Records & figures")).toBeInTheDocument();
    const travel = await screen.findByText("Total travel spend");
    fireEvent.click(travel);
    await waitFor(() => expect(screen.getAllByText("tenant_a").length).toBeGreaterThan(0));
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    await waitFor(() => expect(screen.getByLabelText("Answer")).toBeInTheDocument());
    const presentCall = fetchMock.mock.calls.find(([u]) => u === "/api/v4/present");
    const sent = JSON.parse(presentCall[1].body);
    expect(sent.member2_result).toEqual(rows.member2_result);
    expect(sent.security_context).toEqual({ tenant_id: "tenant_a" });
    vi.unstubAllGlobals();
  });
});
