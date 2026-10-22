"use strict";

const METRICS = {
  finished_water_mgd: { label: "Finished water", unit: "MGD", digits: 2 },
  accord_pond_usage_mg: { label: "Accord Pond usage", unit: "MG/month", digits: 1 },
  accord_pond_level_ft: { label: "Accord Pond level", unit: "feet", digits: 2 },
  precipitation_inches: { label: "Precipitation", unit: "inches", digits: 2 },
  actual_reads_pct: { label: "Actual meter reads", unit: "%", digits: 1 },
  estimated_reads_pct: { label: "Estimated meter reads", unit: "%", digits: 1 },
  customer_contacts: { label: "Customer contacts", unit: "calls", digits: 0 },
  total_work_orders: { label: "Total work orders", unit: "count", digits: 0 },
  maintenance_paid_usd: { label: "Maintenance paid", unit: "USD", digits: 0, currency: true },
  revenue_billed_usd: { label: "Revenue billed", unit: "USD", digits: 0, currency: true },
  revenue_collected_usd: { label: "Revenue collected", unit: "USD", digits: 0, currency: true },
  service_level_pct: { label: "Customer service level", unit: "%", digits: 1 },
};

const state = { data: null, start: null, end: null, metric: "finished_water_mgd", chemical: null };
const $ = (selector) => document.querySelector(selector);
const tooltip = $("#tooltip");

const monthLabel = (value, short = false) => new Intl.DateTimeFormat("en-US", {
  month: short ? "short" : "long", year: "numeric", timeZone: "UTC",
}).format(new Date(`${value}T00:00:00Z`));

function formatValue(value, config = {}) {
  if (value === null || value === undefined) return "Not reported";
  if (config.currency) return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: config.digits ?? 0 }).format(value);
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: config.digits ?? 2, minimumFractionDigits: config.digits ?? 0 }).format(value);
}

function filteredMonths() {
  return state.data.monthly.filter((row) => row.observation_month >= state.start && row.observation_month <= state.end);
}

function setOptions(select, items, selected) {
  select.innerHTML = items.map(([value, label]) => `<option value="${value}"${value === selected ? " selected" : ""}>${label}</option>`).join("");
}

function initControls() {
  const months = state.data.monthly.map((row) => [row.observation_month, monthLabel(row.observation_month)]);
  state.start = months[0][0]; state.end = months.at(-1)[0];
  setOptions($("#start-month"), months, state.start);
  setOptions($("#end-month"), months, state.end);
  setOptions($("#trend-metric"), Object.entries(METRICS).map(([key, value]) => [key, value.label]), state.metric);
  const chemicals = Object.keys(state.data.chemical_units).sort();
  state.chemical = chemicals[0];
  setOptions($("#chemical-metric"), chemicals.map((value) => [value, value.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase())]), state.chemical);

  $("#start-month").addEventListener("change", (event) => { state.start = event.target.value; if (state.start > state.end) { state.end = state.start; $("#end-month").value = state.end; } render(); });
  $("#end-month").addEventListener("change", (event) => { state.end = event.target.value; if (state.end < state.start) { state.start = state.end; $("#start-month").value = state.start; } render(); });
  $("#trend-metric").addEventListener("change", (event) => { state.metric = event.target.value; renderTrend(); });
  $("#chemical-metric").addEventListener("change", (event) => { state.chemical = event.target.value; renderChemical(); });
  $("#reset-filters").addEventListener("click", () => { state.start = months[0][0]; state.end = months.at(-1)[0]; $("#start-month").value = state.start; $("#end-month").value = state.end; render(); });
  $("#download-csv").addEventListener("click", downloadCsv);
}

function showTooltip(event, html) {
  tooltip.innerHTML = html; tooltip.style.left = `${event.clientX}px`; tooltip.style.top = `${event.clientY}px`; tooltip.classList.add("visible");
}
function hideTooltip() { tooltip.classList.remove("visible"); }

function svgLineChart(container, rows, key, config, color = "#0b5fa5") {
  const width = 900, height = 300, margin = { top: 18, right: 25, bottom: 46, left: 66 };
  const usable = rows.filter((row) => row[key] !== null);
  if (!usable.length) { container.innerHTML = "<p>No reported values in this range.</p>"; return; }
  const values = usable.map((row) => row[key]);
  let min = Math.min(...values), max = Math.max(...values); const pad = (max - min || Math.max(Math.abs(max), 1)) * .14; min -= pad; max += pad;
  const x = (index) => margin.left + index * (width - margin.left - margin.right) / Math.max(rows.length - 1, 1);
  const y = (value) => margin.top + (max - value) * (height - margin.top - margin.bottom) / (max - min);
  const points = rows.map((row, index) => row[key] === null ? null : [x(index), y(row[key]), row]).filter(Boolean);
  const ticks = Array.from({ length: 5 }, (_, i) => min + (max - min) * i / 4);
  const line = points.map((point, index) => `${index ? "L" : "M"}${point[0]},${point[1]}`).join(" ");
  const area = `${line} L${points.at(-1)[0]},${height - margin.bottom} L${points[0][0]},${height - margin.bottom} Z`;
  container.innerHTML = `<svg viewBox="0 0 ${width} ${height}" aria-hidden="true"><defs><linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="${color}" stop-opacity=".5"/><stop offset="100%" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>${ticks.map((tick) => `<line class="grid-line" x1="${margin.left}" x2="${width-margin.right}" y1="${y(tick)}" y2="${y(tick)}"/><text class="axis-label" x="${margin.left-10}" y="${y(tick)+4}" text-anchor="end">${formatValue(tick, config)}</text>`).join("")}<line class="axis-line" x1="${margin.left}" x2="${width-margin.right}" y1="${height-margin.bottom}" y2="${height-margin.bottom}"/><path class="trend-area" d="${area}"/><path class="trend-line" style="stroke:${color}" d="${line}"/>${points.map((point) => `<circle class="trend-point" style="stroke:${color}" cx="${point[0]}" cy="${point[1]}" r="5" data-month="${point[2].observation_month}" data-value="${point[2][key]}"><title>${monthLabel(point[2].observation_month)}: ${formatValue(point[2][key], config)} ${config.unit}</title></circle>`).join("")}${rows.map((row, index) => index % Math.max(Math.ceil(rows.length/6),1) === 0 || index === rows.length-1 ? `<text class="axis-label" x="${x(index)}" y="${height-18}" text-anchor="middle">${monthLabel(row.observation_month, true)}</text>` : "").join("")}</svg>`;
  container.querySelectorAll("circle").forEach((circle) => { circle.addEventListener("mousemove", (event) => showTooltip(event, `<strong>${monthLabel(circle.dataset.month)}</strong><br>${formatValue(Number(circle.dataset.value), config)} ${config.unit}`)); circle.addEventListener("mouseleave", hideTooltip); });
}

function renderKpis() {
  const rows = filteredMonths(); const production = rows.map((row) => row.finished_water_mgd).filter((v) => v !== null);
  const peak = rows.reduce((best, row) => !best || row.finished_water_mgd > best.finished_water_mgd ? row : best, null);
  $("#kpi-production").textContent = formatValue(production.reduce((a,b) => a+b, 0)/production.length, { digits: 2 });
  $("#kpi-peak").textContent = `${formatValue(peak.finished_water_mgd, { digits: 2 })} MGD`;
  $("#kpi-peak-month").textContent = monthLabel(peak.observation_month);
  $("#kpi-rain").textContent = formatValue(rows.reduce((sum, row) => sum + (row.precipitation_inches || 0), 0), { digits: 2 });
  $("#kpi-pond").textContent = formatValue(rows.at(-1).accord_pond_level_ft, { digits: 2 });
  $("#kpi-coverage").textContent = `${rows.length * 9}/${rows.length * 9}`;
}

function renderTrend() {
  const rows = filteredMonths(), config = METRICS[state.metric], values = rows.map((row) => row[state.metric]).filter((v) => v !== null);
  $("#trend-title").textContent = config.label;
  const change = values.length > 1 ? values.at(-1) - values[0] : 0;
  $("#trend-change").textContent = `${change >= 0 ? "+" : ""}${formatValue(change, config)} ${config.unit} from range start`;
  svgLineChart($("#trend-chart"), rows, state.metric, config);
}

function renderScatter() {
  const rows = filteredMonths().filter((row) => row.accord_pond_usage_mg !== null && row.finished_water_mgd !== null);
  const width = 520, height = 300, margin = { top: 18, right: 24, bottom: 46, left: 58 };
  const xv = rows.map((r) => r.accord_pond_usage_mg), yv = rows.map((r) => r.finished_water_mgd);
  const minX = Math.min(...xv)*.9, maxX = Math.max(...xv)*1.08, minY = Math.min(...yv)*.94, maxY = Math.max(...yv)*1.04;
  const x = (v) => margin.left + (v-minX)*(width-margin.left-margin.right)/(maxX-minX); const y = (v) => margin.top + (maxY-v)*(height-margin.top-margin.bottom)/(maxY-minY);
  const ticks = [0,1,2,3,4].map((i) => i/4);
  $("#scatter-chart").innerHTML = `<svg viewBox="0 0 ${width} ${height}" aria-hidden="true">${ticks.map((t) => `<line class="grid-line" x1="${margin.left}" x2="${width-margin.right}" y1="${margin.top+t*(height-margin.top-margin.bottom)}" y2="${margin.top+t*(height-margin.top-margin.bottom)}"/>`).join("")}<line class="axis-line" x1="${margin.left}" x2="${width-margin.right}" y1="${height-margin.bottom}" y2="${height-margin.bottom}"/>${rows.map((row) => `<circle class="scatter-point" cx="${x(row.accord_pond_usage_mg)}" cy="${y(row.finished_water_mgd)}" r="7" data-month="${row.observation_month}" data-x="${row.accord_pond_usage_mg}" data-y="${row.finished_water_mgd}"><title>${monthLabel(row.observation_month)}: ${row.accord_pond_usage_mg.toFixed(1)} MG, ${row.finished_water_mgd.toFixed(2)} MGD</title></circle>`).join("")}<text class="axis-label" x="${width/2}" y="${height-10}" text-anchor="middle">Accord Pond usage (MG/month)</text><text class="axis-label" transform="translate(15 ${height/2}) rotate(-90)" text-anchor="middle">Finished water (MGD)</text></svg>`;
  $("#scatter-chart").querySelectorAll("circle").forEach((circle) => { circle.addEventListener("mousemove", (event) => showTooltip(event, `<strong>${monthLabel(circle.dataset.month)}</strong><br>${Number(circle.dataset.x).toFixed(1)} MG pond usage<br>${Number(circle.dataset.y).toFixed(2)} MGD finished water`)); circle.addEventListener("mouseleave", hideTooltip); });
}

function renderChemical() {
  const rows = state.data.chemicals.filter((row) => row.observation_month >= state.start && row.observation_month <= state.end);
  const unit = state.data.chemical_units[state.chemical];
  svgLineChart($("#chemical-chart"), rows, state.chemical, { unit, digits: unit === "tons" ? 2 : 1 }, "#087f8c");
  $("#chemical-unit-note").textContent = unit === "report-specific" ? "The source does not define this unit consistently; values are shown without conversion." : `Reported in ${unit}.`;
}

function renderAnomalies() {
  const rows = state.data.anomalies.filter((row) => row.observation_month >= state.start && row.observation_month <= state.end);
  $("#anomaly-count").textContent = `${rows.length} flag${rows.length === 1 ? "" : "s"}`;
  $("#anomaly-table").innerHTML = rows.length ? rows.map((row) => `<tr><td>${monthLabel(row.observation_month)}</td><td>${METRICS[row.metric]?.label || row.metric.replaceAll("_", " ")}</td><td>${formatValue(row.value, METRICS[row.metric] || { digits: 2 })}</td><td>${row.z_score.toFixed(2)}</td></tr>`).join("") : `<tr><td colspan="4">No two-standard-deviation flags in this range.</td></tr>`;
}

function renderCoverage() {
  const labels = Object.keys(state.data.coverage[0]).filter((key) => key !== "observation_month");
  $("#coverage-grid").innerHTML = labels.map((key) => `<div class="coverage-item">${key.replaceAll("_", " ")} · 15/15</div>`).join("");
  $("#limitations").innerHTML = state.data.limitations.map((item) => `<li>${item}</li>`).join("");
}

function renderTable() {
  $("#monthly-table").innerHTML = filteredMonths().map((row) => `<tr><td>${monthLabel(row.observation_month, true)}</td><td>${formatValue(row.finished_water_mgd,{digits:2})} MGD</td><td>${formatValue(row.accord_pond_usage_mg,{digits:1})} MG</td><td>${formatValue(row.precipitation_inches,{digits:2})} in</td><td>${formatValue(row.actual_reads_pct,{digits:1})}%</td><td>${formatValue(row.total_work_orders,{digits:0})}</td><td>${formatValue(row.maintenance_paid_usd,{currency:true,digits:0})}</td></tr>`).join("");
}

function downloadCsv() {
  const rows = filteredMonths(); const columns = ["observation_month", ...Object.keys(METRICS)];
  const quote = (value) => value === null ? "" : `"${String(value).replaceAll('"','""')}"`;
  const csv = [columns.join(","), ...rows.map((row) => columns.map((column) => quote(row[column])).join(","))].join("\n");
  const link = document.createElement("a"); link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" })); link.download = `weir-river-${state.start}-to-${state.end}.csv`; link.click(); URL.revokeObjectURL(link.href);
}

function render() { renderKpis(); renderTrend(); renderScatter(); renderChemical(); renderAnomalies(); renderTable(); }

async function main() {
  try {
    const response = await fetch("data/dashboard.json"); if (!response.ok) throw new Error(`Data request failed (${response.status})`);
    state.data = await response.json(); initControls(); renderCoverage(); render();
  } catch (error) {
    document.querySelector("main").innerHTML = `<div class="error"><strong>Dashboard could not load.</strong><br>${error.message}<br>Serve this directory over HTTP after running <code>python dashboard/build_dashboard_data.py</code>.</div>`;
  }
}

main();
