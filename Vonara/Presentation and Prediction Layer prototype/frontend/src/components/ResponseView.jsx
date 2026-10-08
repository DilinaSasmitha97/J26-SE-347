// Renders one /api/v4/present envelope following the client rendering
// contract (team_interface_contract.md): render from `response`, in the order
// of `response.blocks_emitted`, branching on key presence. Key figures and
// the tabbed panels are drawn from the envelope's other sections (summary
// claims, prediction, analysis) and never replace an emitted block.

import { useState } from "react";
import { humanize } from "../format.js";
import { AnswerCard, ChartBlock, ForecastNotice, KeyFigures, SummaryBlock, TableBlock } from "./blocks.jsx";
import Icon from "./icons.jsx";
import { AnomalyPanel, DetailsPanel, SHAPE_LABEL, TabPanel, Tabs, WhatIfPanel, WorkingPanel } from "./panels.jsx";

const SHAPE_ICON = {
  SINGLE_ANSWER: "figure",
  SHORT_SUMMARY: "sparkle",
  TABLE_CONTENT: "table",
  CHART: "trend",
  MIXED_SUMMARY: "layers",
};

function ResultHeader({ question, envelope }) {
  const ri = envelope.response?.response_intent || {};
  const intent = envelope.analysis?.intent || {};
  const ms = envelope.profiling?.total_execution_ms;
  return (
    <header>
      <p className="eyebrow">Result</p>
      {question && <h2 className="result-title">{question}</h2>}
      <div className="pills">
        <span className="pill pill-accent">
          <Icon name={SHAPE_ICON[ri.intent] || "layers"} size={13} />
          {SHAPE_LABEL[ri.intent] || ri.intent}
        </span>
        {intent.primary_intent && (
          <span className="pill" title={intent.rationale}>
            {humanize(intent.primary_intent.toLowerCase())} · {Math.round((intent.confidence || 0) * 100)}%
          </span>
        )}
        {ms !== undefined && (
          <span className="pill">
            <Icon name="clock" size={13} />
            {Math.round(ms)} ms{envelope.cache?.hit ? " · cached" : ""}
          </span>
        )}
      </div>
    </header>
  );
}

/**
 * `layout="workspace"` is the full-screen ask view: the result on the left
 * (the chart grows to the free height) and the analysis tabs in a side pane;
 * each side scrolls on its own. The default stacks everything in one column.
 */
export default function ResponseView({ envelope, question, onSimulate, embed, layout = "stack" }) {
  const pred = envelope?.prediction || {};
  const anomaly = pred.stage_5_anomaly;
  const anomalyCount = anomaly && anomaly.evaluated
    ? (anomaly.historical_anomalies || []).length + (anomaly.predictive_warnings || []).length
    : 0;
  const forecastMade = Boolean(pred.stage_4_forecast && pred.stage_4_forecast.generated);
  const canSimulate = forecastMade && Boolean(onSimulate);
  const [tab, setTab] = useState(anomalyCount > 0 ? "anomalies" : canSimulate ? "whatif" : "working");
  if (!envelope) return null;

  const response = envelope.response || {};
  const ri = response.response_intent || {};
  const blocks = response.blocks_emitted || [];
  const masked = (envelope.input && envelope.input.masked_columns) || {};
  const notRequest = ri.is_data_request === false;
  const showFigures = blocks.includes("CHART") && !blocks.includes("ANSWER")
    && envelope.analysis?.intent?.primary_intent !== "DETAIL_LOOKUP";
  const claimCount = envelope.summary?.claims?.length || 0;

  const tabs = [
    { id: "anomalies", label: "Anomalies", icon: "alert", count: anomaly?.evaluated ? anomalyCount : undefined },
    {
      id: "whatif",
      label: "What-if",
      icon: "sliders",
      disabled: !canSimulate,
      disabledReason: "A what-if needs a forecast: ask to predict or forecast the next periods",
    },
    { id: "working", label: "Show the working", icon: "check", count: claimCount },
    { id: "details", label: "Details", icon: "info" },
  ];

  const workspace = layout === "workspace";
  const main = (
    <>
      <ResultHeader question={question} envelope={envelope} />

      {notRequest && (
        <div className="notice notice-warning" role="status">
          <Icon name="info" size={18} />
          <div>
            <strong>That doesn't look like a question about the data.</strong>
            Try asking for a total, a trend, a comparison or a list.
          </div>
        </div>
      )}

      <ForecastNotice notice={response.forecast_notice} />

      {showFigures && <KeyFigures envelope={envelope} />}

      {blocks.map((name) => {
        if (name === "ANSWER") return <AnswerCard key={name} answer={response.answer} />;
        if (name === "SUMMARY")
          return <SummaryBlock key={name} summary={response.summary} envelopeSummary={envelope.summary} />;
        if (name === "TABLE") return <TableBlock key={name} table={response.table} maskedColumns={masked} />;
        if (name === "CHART")
          return (
            <ChartBlock key={name} chart={response.chart} visualization={envelope.visualization} embed={embed}
              fill={workspace} />
          );
        return null;
      })}
    </>
  );
  const analysis = (
      <section className="card" aria-label="Analysis">
        <Tabs tabs={tabs} active={tab} onChange={setTab} label="Analysis" />
        <TabPanel id="anomalies" active={tab}>
          <AnomalyPanel anomaly={anomaly} />
        </TabPanel>
        <TabPanel id="whatif" active={tab}>
          {canSimulate && <WhatIfPanel onSimulate={onSimulate} embed={embed} />}
        </TabPanel>
        <TabPanel id="working" active={tab}>
          <WorkingPanel summary={envelope.summary} />
        </TabPanel>
        <TabPanel id="details" active={tab}>
          <DetailsPanel envelope={envelope} />
        </TabPanel>
      </section>
  );

  if (workspace) {
    return (
      <div className="workspace">
        <div className="ws-main">{main}</div>
        <div className="ws-side">{analysis}</div>
      </div>
    );
  }
  return (
    <div className="stack">
      {main}
      {analysis}
    </div>
  );
}
