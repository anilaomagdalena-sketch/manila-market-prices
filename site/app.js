(() => {
  "use strict";

  const chartCanvas = document.querySelector("#chart");
  const select = document.querySelector("#item");
  const categories = document.querySelector("#categories");
  const periods = document.querySelector("#periods");
  const empty = document.querySelector("#empty");
  let data;
  let active;
  let period = "all";
  let chart;

  const dayNumber = iso => Math.round(Date.parse(`${iso}T00:00:00Z`) / 86400000);
  const isoDate = day => new Date(day * 86400000).toISOString().slice(0, 10);
  const japaneseDate = iso => {
    const [year, month, day] = iso.split("-").map(Number);
    return `${year}年${month}月${day}日`;
  };
  const yen = value => `₱${Number(value).toLocaleString("ja-JP", { maximumFractionDigits: 2 })}`;

  function label(item) {
    const other = [item.name_tl, item.name_en].filter(Boolean).join("／");
    return other ? `${item.name_ja}（${other}）` : item.name_ja;
  }

  function currentRange() {
    if (period === "all") return -Infinity;
    const today = new Date(`${data.updated}T00:00:00Z`);
    today.setUTCFullYear(today.getUTCFullYear() - Number(period));
    return Math.round(today.getTime() / 86400000);
  }

  function points(item) {
    const from = currentRange();
    return {
      ncr: item.ncr.filter(row => dayNumber(row[0]) >= from),
      cartimar: item.cartimar.filter(row => dayNumber(row[0]) >= from),
      own: item.own.filter(row => dayNumber(row[0]) >= from)
    };
  }

  function brokenLine(rows, valueIndex) {
    const output = [];
    for (let i = 0; i < rows.length; i++) {
      const current = dayNumber(rows[i][0]);
      if (i && current - dayNumber(rows[i - 1][0]) >= 28) {
        output.push({ x: dayNumber(rows[i - 1][0]) + 7, y: null });
      }
      output.push({ x: current, y: rows[i][valueIndex], basis: rows[i][4], low: rows[i][2], high: rows[i][3] });
    }
    return output;
  }

  function datasets(series) {
    const result = [];
    if (series.ncr.length) {
      result.push({ label: "安値", data: brokenLine(series.ncr.filter(row => row[2] !== null), 2),
                    borderWidth: 0, pointRadius: 0, backgroundColor: "transparent", spanGaps: false });
      result.push({ label: "安値〜高値", data: brokenLine(series.ncr.filter(row => row[3] !== null), 3),
                    borderWidth: 0, pointRadius: 0, backgroundColor: "rgba(27,110,140,.15)", fill: "-1", spanGaps: false });
      result.push({ label: "首都圏の市場平均（農業省調べ）", data: brokenLine(series.ncr, 1),
                    borderColor: "#1B6E8C", borderWidth: 2, pointRadius: 2, tension: 0, spanGaps: false,
                    segment: { borderDash: context => context.p1.raw?.basis === "midpoint" ? [6, 4] : [] } });
    }
    if (series.cartimar.length) {
      result.push({ label: "カルティマール市場（農業省調べ）", data: brokenLine(series.cartimar, 1),
                    borderColor: "#B4531A", borderWidth: 2, borderDash: [2, 3], pointRadius: 0, spanGaps: false });
    }
    if (series.own.length) {
      result.push({ label: "カルティマールでの実測（著者）",
                    data: series.own.map(row => ({ x: dayNumber(row[0]), y: row[1] })),
                    showLine: false, pointStyle: "rectRot", pointRadius: 5, pointBorderWidth: 1.5,
                    pointBorderColor: "#fff", pointBackgroundColor: "#1F2933" });
    }
    return result;
  }

  function renderLegend(series) {
    const legend = document.querySelector("#legend");
    legend.replaceChildren();
    const entries = [];
    if (series.ncr.length) {
      entries.push(["", "首都圏の市場平均（農業省調べ）"], ["band", "安値〜高値"]);
    }
    if (series.cartimar.length) entries.push(["cartimar", "カルティマール市場（農業省調べ）"]);
    if (series.own.length) entries.push(["own", "カルティマールでの実測（著者）"]);
    for (const [kind, name] of entries) {
      const entry = document.createElement("span");
      const mark = document.createElement("i");
      mark.className = `mark ${kind}`;
      mark.setAttribute("aria-hidden", "true");
      entry.append(mark, document.createTextNode(name));
      legend.append(entry);
    }
  }

  function comparison(current, previous) {
    if (!previous) return "—";
    const change = Math.round((current / previous - 1) * 100);
    if (change === 0) return "±0%";
    return `${change > 0 ? "▲+" : "▼−"}${Math.abs(change)}%`;
  }

  function renderStats(item) {
    const box = document.querySelector("#stats");
    box.replaceChildren();
    const ncr = item.ncr;
    const latest = ncr.at(-1);
    const ownLatest = item.own.at(-1);
    let first, previous = "—", year = "—", dateText = "";
    if (latest) {
      first = yen(latest[1]);
      dateText = `${japaneseDate(latest[0])}の週`;
      const prior = ncr.at(-2);
      if (prior && dayNumber(latest[0]) - dayNumber(prior[0]) === 7) previous = comparison(latest[1], prior[1]);
      const earlier = ncr.filter(row => Math.abs(dayNumber(latest[0]) - dayNumber(row[0]) - 364) <= 7).at(-1);
      if (earlier) year = comparison(latest[1], earlier[1]);
    } else if (ownLatest) {
      first = yen(ownLatest[1]);
      dateText = japaneseDate(ownLatest[0]);
    } else {
      first = "—";
    }
    for (const [heading, value, sub] of [["最新の価格", first, dateText], ["前週比", previous, ""], ["前年同週比", year, ""]]) {
      const cell = document.createElement("div");
      const title = document.createElement("dt");
      title.textContent = heading;
      const detail = document.createElement("dd");
      detail.textContent = value;
      if (sub) {
        const small = document.createElement("small");
        small.textContent = sub;
        detail.append(small);
      }
      cell.append(title, detail);
      box.append(cell);
    }
  }

  function renderNotes(series) {
    document.querySelector("#midpoint-note").hidden = !series.ncr.some(row => row[4] === "midpoint");
    document.querySelector("#own-note").hidden = !series.own.length;
    document.querySelector("#source").innerHTML = `出典：<a href="https://www.da.gov.ph/price-monitoring/" target="_blank" rel="noopener">フィリピン農業省 DA-AMAS Bantay Presyo</a> ／ 最終更新 ${japaneseDate(data.updated)}（データは${japaneseDate(data.latest_report)}分まで）`;
  }

  function renderChart(series) {
    chartCanvas.removeAttribute("data-ready");
    if (chart) chart.destroy();
    empty.hidden = !!(series.ncr.length || series.cartimar.length || series.own.length);
    const allDays = [...series.ncr, ...series.cartimar, ...series.own].map(row => dayNumber(row[0]));
    const min = allDays.length ? Math.min(...allDays) : dayNumber(data.updated) - 365;
    const max = allDays.length ? Math.max(...allDays) : dayNumber(data.updated);
    chart = new Chart(chartCanvas, {
      type: "line",
      data: { datasets: datasets(series) },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false, parsing: false,
        interaction: { mode: "nearest", intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: items => `${japaneseDate(isoDate(items[0].parsed.x))}の週`,
              label: item => item.dataset.label === "安値〜高値" ?
                `安値〜高値：${yen(item.raw.low)}〜${yen(item.raw.high)}` :
                `${item.dataset.label}：${yen(item.parsed.y)}`
            },
            filter: item => item.dataset.label !== "安値"
          }
        },
        scales: {
          x: { type: "linear", min: min - 7, max: max + 7,
               ticks: { maxTicksLimit: 7, callback: value => {
                 const date = new Date(value * 86400000);
                 return period === "1" ? `${date.getUTCMonth() + 1}月` : String(date.getUTCFullYear());
               } } },
          y: { beginAtZero: true, title: { display: true, text: `1${active.unit}あたり（ペソ）` },
               ticks: { callback: value => `₱${value}` } }
        }
      }
    });
    chartCanvas.dataset.ready = "1";
  }

  function render() {
    const series = points(active);
    for (const button of categories.querySelectorAll("[role=tab]")) {
      button.setAttribute("aria-selected", String(button.dataset.category === active.category));
    }
    for (const button of periods.querySelectorAll("button")) {
      button.setAttribute("aria-pressed", String(button.dataset.period === period));
    }
    select.replaceChildren();
    for (const item of data.items.filter(item => item.category === active.category)) {
      const option = document.createElement("option");
      option.value = item.id;
      option.textContent = label(item);
      select.append(option);
    }
    select.value = active.id;
    renderLegend(series);
    renderStats(active);
    renderNotes(series);
    renderChart(series);
  }

  async function init() {
    const params = new URLSearchParams(location.search);
    const response = await fetch(params.get("data") || "data.json");
    if (!response.ok) throw new Error(`data fetch failed: ${response.status}`);
    data = await response.json();
    active = data.items.find(item => item.id === params.get("item")) || data.items[0];
    for (const category of data.categories.filter(category => data.items.some(item => item.category === category.id))) {
      const button = document.createElement("button");
      button.type = "button";
      button.role = "tab";
      button.dataset.category = category.id;
      button.textContent = category.label;
      button.addEventListener("click", () => {
        active = data.items.find(item => item.category === category.id);
        render();
      });
      categories.append(button);
    }
    select.addEventListener("change", () => {
      active = data.items.find(item => item.id === select.value);
      render();
    });
    periods.addEventListener("click", event => {
      const button = event.target.closest("button[data-period]");
      if (!button) return;
      period = button.dataset.period;
      render();
    });
    render();
  }

  init().catch(error => { console.error(error); empty.hidden = false; });
})();
