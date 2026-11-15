/* OI playbook — static viewer. Fixed file: only data/latest.json changes per publish. */
(function () {
  "use strict";

  var DATA_URL = "data/latest.json";
  var REFRESH_MS = 5 * 60 * 1000;
  var TZ = "Asia/Ho_Chi_Minh";
  var SIDE_ORDER = { long: 0, short: 1, none: 2, error: 3 };

  var state = {
    data: null,
    generatedAt: null,
    fetchError: null,
    sort: { key: "symbol", dir: 1 },
    filters: { symbol: "", tf: "", side: "" },
    charts: [],
    overlay: {}
  };

  var $ = function (id) { return document.getElementById(id); };

  // ---------- formatting ----------
  var dtParts = new Intl.DateTimeFormat("en-GB", {
    timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23"
  });

  function parts(date) {
    var o = {};
    dtParts.formatToParts(date).forEach(function (p) { o[p.type] = p.value; });
    return o;
  }

  function fmtVN(date, withDate) {
    if (!(date instanceof Date) || isNaN(date)) return "—";
    var p = parts(date);
    var hm = p.hour + ":" + p.minute;
    return withDate === false ? hm : p.year + "-" + p.month + "-" + p.day + " " + hm;
  }

  // "YYYY-MM-DD HH:MM" (UTC, from the scanner) → Date
  function parseBarUTC(s) {
    var m = /^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?/.exec(s || "");
    if (!m) return null;
    return new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +(m[4] || 0), +(m[5] || 0)));
  }

  function fmtBar(s) {
    var d = parseBarUTC(s);
    return d ? fmtVN(d) : "—";
  }

  function fmtNum(v, digits) {
    if (v === null || v === undefined || v === "" || isNaN(+v)) return "—";
    var d = digits === undefined ? 2 : digits;
    return (+v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
  }

  function fmtPrice(v) {
    if (v === null || v === undefined || isNaN(+v)) return "—";
    var a = Math.abs(+v);
    return fmtNum(v, a >= 1000 ? 2 : a >= 1 ? 3 : 5);
  }

  var compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 2 });

  function fmtAge(ms) {
    var m = Math.round(ms / 60000);
    if (m < 1) return "vừa xong";
    if (m < 60) return m + " phút trước";
    var h = Math.floor(m / 60);
    if (h < 48) return h + " giờ " + (m % 60) + " phút trước";
    return Math.floor(h / 24) + " ngày trước";
  }

  function esc(s) {
    return String(s === null || s === undefined ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  // Tiny inline markdown: `code` and **bold** (input is escaped first).
  function md(s) {
    return esc(s)
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  }

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function sideLabel(side) {
    return side === "error" ? "lỗi" : side || "none";
  }

  // ---------- theme ----------
  function effectiveTheme() {
    var t = document.documentElement.dataset.theme;
    if (t === "light" || t === "dark") return t;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function setTheme(t) {
    document.documentElement.dataset.theme = t;
    try { localStorage.setItem("oi-theme", t); } catch (e) { /* storage blocked */ }
    updateThemeButton();
    restyleCharts();
  }

  function updateThemeButton() {
    $("theme-btn").textContent = effectiveTheme() === "dark" ? "Sáng" : "Tối";
  }

  // ---------- banners ----------
  function renderBanners() {
    var box = $("banners");
    box.textContent = "";
    var d = state.data;
    if (state.fetchError && d) {
      var b = el("div", "banner err");
      b.textContent = "Không tải được dữ liệu mới (" + state.fetchError + "). Đang hiển thị bản lúc " +
        fmtVN(state.generatedAt) + ".";
      box.appendChild(b);
    }
    if (d && state.generatedAt) {
      var age = Date.now() - state.generatedAt.getTime();
      var cycle = Math.max(1, +d.refresh_minutes || 15) * 60000;
      if (age > 2 * cycle) {
        var w = el("div", "banner warn");
        w.textContent = "Data cũ: cập nhật lần cuối " + fmtVN(state.generatedAt) + " (" + fmtAge(age) +
          "), quá 2× chu kỳ " + (d.refresh_minutes || 15) + " phút. Máy xuất data có thể đang tắt.";
        box.appendChild(w);
      }
    }
    if (d && state.generatedAt) {
      $("meta").textContent = "Cập nhật " + fmtVN(state.generatedAt) + " (giờ VN) · " +
        fmtAge(Date.now() - state.generatedAt.getTime()) + " · v" + d.version;
    }
  }

  // ---------- playbook ----------
  function renderPlaybook(pb) {
    $("pb-caption").innerHTML = md(pb.caption);
    var sc = $("pb-scenarios");
    sc.textContent = "";
    (pb.scenarios || []).forEach(function (s) {
      var div = el("div", "scenario");
      div.innerHTML = "<strong><code>" + esc(s.name) + "</code></strong><p>" + esc(s.desc) + "</p>" +
        (s.why ? '<p class="muted small">' + esc(s.why) + "</p>" : "");
      sc.appendChild(div);
    });
    var tb = $("pb-exits");
    tb.textContent = "";
    (pb.exits || []).forEach(function (x) {
      var tr = el("tr");
      tr.innerHTML = "<td>" + esc(x.tf) + '</td><td class="num">' + fmtNum(x.tp_pct, 1) +
        '</td><td class="num">' + fmtNum(x.sl_pct, 1) + '</td><td class="num">' + fmtNum(x.rr, 2) +
        '</td><td class="num">' + esc(x.max_hold_bars) + "</td>";
      tb.appendChild(tr);
    });
    $("pb-exit-note").textContent = pb.exit_note || "";
    var ops = $("pb-ops");
    ops.textContent = "";
    (pb.ops || []).forEach(function (line) {
      var li = el("li");
      li.innerHTML = md(line);
      ops.appendChild(li);
    });
    $("disclaimer").textContent = pb.disclaimer || "ALERT ONLY — not investment advice";
    $("playbook").hidden = false;
  }

  // ---------- summary ----------
  function fillSelect(sel, values) {
    var cur = sel.value;
    while (sel.options.length > 1) sel.remove(1);
    values.forEach(function (v) {
      var o = el("option", null, v);
      o.value = v;
      sel.appendChild(o);
    });
    sel.value = values.indexOf(cur) >= 0 ? cur : "";
  }

  function uniq(arr) {
    return arr.filter(function (v, i) { return arr.indexOf(v) === i; });
  }

  function sortVal(r, key) {
    if (key === "side") return SIDE_ORDER[r.side] !== undefined ? SIDE_ORDER[r.side] : 9;
    if (key === "scenarios") return (r.scenarios || []).join(",");
    if (key === "interval") return parseInt(r.interval, 10) * (/d$/.test(r.interval) ? 24 : 1);
    var v = r[key];
    return v === null || v === undefined ? null : v;
  }

  function renderSummary() {
    var rows = (state.data.summary || []).slice();
    var f = state.filters;
    rows = rows.filter(function (r) {
      return (!f.symbol || r.symbol === f.symbol) && (!f.tf || r.interval === f.tf) && (!f.side || r.side === f.side);
    });
    var k = state.sort.key, dir = state.sort.dir;
    rows.sort(function (a, b) {
      var x = sortVal(a, k), y = sortVal(b, k);
      if (x === y) return 0;
      if (x === null) return 1;
      if (y === null) return -1;
      return (x < y ? -1 : 1) * dir;
    });

    document.querySelectorAll(".summary-table th[data-sort]").forEach(function (th) {
      if (th.dataset.sort === k) th.setAttribute("aria-sort", dir > 0 ? "ascending" : "descending");
      else th.removeAttribute("aria-sort");
    });

    var tb = $("summary-body");
    tb.textContent = "";
    rows.forEach(function (r) {
      var tr = el("tr");
      tr.tabIndex = 0;
      tr.dataset.target = cardId(r);
      var cells = [
        ["Symbol", esc(r.symbol), ""],
        ["TF", esc(r.interval), ""],
        ["Tín hiệu", '<span class="badge ' + esc(r.side) + '">' + esc(sideLabel(r.side)) + "</span>", ""],
        ["Nến (VN)", esc(fmtBar(r.bar_time)), ""],
        ["Entry", fmtPrice(r.entry), "num"],
        ["SL", fmtPrice(r.stop), "num"],
        ["TP", fmtPrice(r.target), "num"],
        ["Scenarios", (r.scenarios || []).length ? (r.scenarios || []).map(function (s) { return "<code>" + esc(s) + "</code>"; }).join(" ") : "—", ""]
      ];
      cells.forEach(function (c) {
        var td = el("td", c[2]);
        td.dataset.label = c[0];
        td.innerHTML = c[1];
        tr.appendChild(td);
      });
      tb.appendChild(tr);
    });
    $("summary-empty").hidden = rows.length > 0;
    $("summary").hidden = false;
  }

  function cardId(r) {
    return "card-" + String(r.symbol + "-" + r.interval).replace(/[^A-Za-z0-9-]/g, "");
  }

  function jumpToCard(id) {
    var c = document.getElementById(id);
    if (!c) return;
    c.scrollIntoView({ behavior: "smooth", block: "start" });
    c.classList.add("flash");
    setTimeout(function () { c.classList.remove("flash"); }, 1400);
  }

  // ---------- detail cards ----------
  var FEATURE_LABELS = [
    ["oi_chg_3_pct", "OI Δ3d %", 2],
    ["oi_z_30", "OI z30", 2],
    ["funding_z_30", "Fund z", 2],
    ["usdt_d", "USDT.D", 3],
    ["usdt_d_chg_3", "USDT.D Δ3d", 3],
    ["usdt_d_z_30", "USDT.D z", 2],
    ["regime_ema", "EMA", null],
    ["usdtd_risk_off", "risk-off", null],
    ["usdtd_risk_on", "risk-on", null]
  ];

  function renderCards() {
    destroyCharts();
    var box = $("cards");
    box.textContent = "";
    var tpl = $("card-tpl");
    (state.data.details || []).forEach(function (d) {
      var node = tpl.content.firstElementChild.cloneNode(true);
      var side = d.side || "none";
      node.id = cardId(d);
      node.classList.add(side);
      var badge = node.querySelector(".badge");
      badge.classList.add(side);
      badge.textContent = side === "none" ? "none" : sideLabel(side);
      node.querySelector(".card-title").textContent = d.symbol + " · " + d.interval;

      var msg = node.querySelector(".card-msg");
      var featErr = d.features && d.features.error;
      if (!d.ok) {
        msg.hidden = false;
        msg.classList.add("err");
        msg.textContent = "Scan lỗi: " + (d.error || "không rõ");
      } else if (featErr) {
        msg.hidden = false;
        msg.textContent = "Không đủ dữ liệu: " + featErr;
      } else if (side === "none") {
        msg.hidden = false;
        msg.textContent = "Không vào lệnh.";
      }

      var set = function (k, v) { node.querySelector('[data-k="' + k + '"]').textContent = v; };
      set("bar", fmtBar(d.bar_time));
      set("entry", fmtPrice(d.entry !== null && d.entry !== undefined ? d.entry : d.close));
      set("stop", fmtPrice(d.stop));
      set("target", fmtPrice(d.target));
      if (!d.ok) node.querySelector(".metrics").hidden = true;

      var plan = node.querySelector(".plan");
      if (d.sl_pct) {
        plan.textContent = "Plan: TP " + fmtNum(d.tp_pct * 100, 1) + "% / SL " + fmtNum(d.sl_pct * 100, 1) +
          "% · R:R " + fmtNum(d.tp_pct / d.sl_pct, 2) + ":1" + (d.oi_source ? " · OI: " + d.oi_source : "");
      } else {
        plan.hidden = true;
      }

      var trig = node.querySelector(".triggers");
      if ((d.scenarios || []).length) {
        trig.innerHTML = "<strong class=\"small\">Triggers</strong><ul>" + d.scenarios.map(function (s) {
          return "<li><code>" + esc(s.scenario) + "</code> (" + esc(s.side) + ") — " + esc(s.desc) + "</li>";
        }).join("") + "</ul>";
      } else {
        trig.hidden = true;
      }

      var feats = node.querySelector(".features");
      var f = d.features || {};
      if (d.ok && !featErr) {
        FEATURE_LABELS.forEach(function (fl) {
          if (!(fl[0] in f)) return;
          var v = f[fl[0]];
          var div = el("div");
          div.appendChild(el("dt", null, fl[1]));
          div.appendChild(el("dd", null, typeof v === "boolean" ? (v ? "yes" : "no") : fl[2] === null ? String(v === null ? "—" : v) : fmtNum(v, fl[2])));
          feats.appendChild(div);
        });
      } else {
        feats.hidden = true;
      }

      if (d.telegram_preview) {
        var det = node.querySelector(".preview");
        det.hidden = false;
        det.querySelector("pre").textContent = d.telegram_preview;
      }

      box.appendChild(node);
      setupChart(node, d);
    });
    $("details").hidden = false;
  }

  // ---------- charts ----------
  function chartColors() {
    return {
      bg: cssVar("--surface"),
      text: cssVar("--muted"),
      grid: cssVar("--border"),
      line: cssVar("--chart-line"),
      overlay: cssVar("--chart-overlay"),
      long: cssVar("--long"),
      short: cssVar("--short")
    };
  }

  function chartOptions(c) {
    return {
      autoSize: true,
      layout: { background: { type: "solid", color: c.bg }, textColor: c.text, fontSize: 11 },
      grid: { vertLines: { color: c.grid, style: 1 }, horzLines: { color: c.grid, style: 1 } },
      rightPriceScale: { borderVisible: false },
      leftPriceScale: { visible: true, borderVisible: false },
      timeScale: {
        borderVisible: false, timeVisible: true, secondsVisible: false,
        tickMarkFormatter: function (t, type) {
          var p = parts(new Date(t * 1000));
          if (type === 0) return p.year;
          if (type === 1) return p.month + "/" + p.year.slice(2);
          if (type === 2) return p.day + "/" + p.month;
          return p.hour + ":" + p.minute;
        }
      },
      localization: {
        timeFormatter: function (t) { return fmtVN(new Date(t * 1000)); }
      },
      crosshair: { mode: 0 },
      handleScroll: { vertTouchDrag: false },
      handleScale: { axisPressedMouseMove: false }
    };
  }

  function seriesPoints(s, key) {
    var out = [];
    var t = s.t || [];
    var v = s[key] || [];
    for (var i = 0; i < t.length; i++) {
      var y = v[i];
      if (y === null || y === undefined || isNaN(+y)) continue;
      out.push({ time: t[i], value: key === "funding" ? +y * 100 : +y });
    }
    return out;
  }

  var OVERLAY_FMT = {
    oi_usd: { label: "OI (USD)", fmt: function (v) { return compact.format(v); } },
    funding: { label: "Funding %", fmt: function (v) { return v.toFixed(4) + "%"; } },
    usdt_d: { label: "USDT.D %", fmt: function (v) { return v.toFixed(3); } }
  };

  function setupChart(node, d) {
    var holder = node.querySelector(".chart");
    var wrap = node.querySelector(".chart-wrap");
    var s = d.series;
    if (!s || !(s.t || []).length) {
      wrap.hidden = true;
      return;
    }
    if (typeof window.LightweightCharts === "undefined") {
      holder.className = "chart-fallback muted small";
      holder.textContent = "Không tải được thư viện chart (CDN). Số liệu phía trên vẫn đúng.";
      node.querySelector(".chart-overlay").hidden = true;
      return;
    }
    var id = cardId(d);
    var sel = node.querySelector(".chart-overlay");
    sel.value = state.overlay[id] || "oi_usd";
    holder.setAttribute("aria-label", "Giá đóng cửa " + d.symbol + " " + d.interval + " và " + OVERLAY_FMT[sel.value].label);

    var c = chartColors();
    var chart = window.LightweightCharts.createChart(holder, chartOptions(c));
    var price = chart.addLineSeries({ color: c.line, lineWidth: 2, priceScaleId: "right", priceLineVisible: false, lastValueVisible: true });
    price.setData(seriesPoints(s, "close"));
    var over = chart.addLineSeries({ color: c.overlay, lineWidth: 1, priceScaleId: "left", priceLineVisible: false, lastValueVisible: false });

    if (d.side === "long" || d.side === "short") {
      if (d.entry != null) price.createPriceLine({ price: d.entry, color: c.text, lineWidth: 1, lineStyle: 2, title: "entry" });
      if (d.stop != null) price.createPriceLine({ price: d.stop, color: c.short, lineWidth: 1, lineStyle: 2, title: "SL" });
      if (d.target != null) price.createPriceLine({ price: d.target, color: c.long, lineWidth: 1, lineStyle: 2, title: "TP" });
    }

    var legend = node.querySelector(".chart-legend");
    function applyOverlay(key) {
      var cfg = OVERLAY_FMT[key];
      over.applyOptions({ priceFormat: { type: "custom", formatter: cfg.fmt, minMove: key === "funding" ? 0.0001 : 0.001 } });
      over.setData(seriesPoints(s, key));
      legend.textContent = "Giá (phải) · " + cfg.label + " (trái)";
      chart.timeScale().fitContent();
    }
    applyOverlay(sel.value);
    // autoSize measures after layout; refit once the real width is known.
    requestAnimationFrame(function () { chart.timeScale().fitContent(); });
    setTimeout(function () { chart.timeScale().fitContent(); }, 250);
    sel.addEventListener("change", function () {
      state.overlay[id] = sel.value;
      applyOverlay(sel.value);
    });
    state.charts.push({ chart: chart, price: price, over: over });
  }

  function restyleCharts() {
    if (!state.charts.length) return;
    var c = chartColors();
    state.charts.forEach(function (x) {
      x.chart.applyOptions({
        layout: { background: { type: "solid", color: c.bg }, textColor: c.text },
        grid: { vertLines: { color: c.grid }, horzLines: { color: c.grid } }
      });
      x.price.applyOptions({ color: c.line });
      x.over.applyOptions({ color: c.overlay });
    });
  }

  function destroyCharts() {
    state.charts.forEach(function (x) { try { x.chart.remove(); } catch (e) { /* already gone */ } });
    state.charts = [];
  }

  // ---------- data ----------
  function validShape(d) {
    return d && typeof d === "object" && typeof d.generated_at === "string" &&
      d.playbook && Array.isArray(d.summary) && Array.isArray(d.details);
  }

  function showFatal(msg) {
    $("error-text").textContent = msg;
    $("error-state").hidden = false;
    $("meta").textContent = "Không có dữ liệu";
  }

  function load() {
    var btn = $("refresh-btn");
    btn.disabled = true;
    return fetch(DATA_URL + "?t=" + Date.now(), { cache: "no-store" })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json().catch(function () { throw new Error("JSON không hợp lệ"); });
      })
      .then(function (d) {
        if (!validShape(d)) throw new Error("sai định dạng dữ liệu");
        var gen = new Date(d.generated_at);
        if (isNaN(gen)) throw new Error("generated_at không hợp lệ");
        state.fetchError = null;
        $("error-state").hidden = true;
        var changed = !state.data || state.data.generated_at !== d.generated_at;
        state.data = d;
        state.generatedAt = gen;
        if (changed) {
          renderPlaybook(d.playbook);
          fillSelect($("f-symbol"), uniq(d.summary.map(function (r) { return r.symbol; })));
          fillSelect($("f-tf"), uniq(d.summary.map(function (r) { return r.interval; })));
          state.filters.symbol = $("f-symbol").value;
          state.filters.tf = $("f-tf").value;
          renderSummary();
          renderCards();
        }
      })
      .catch(function (err) {
        var msg = (err && err.message) || "lỗi mạng";
        if (/Failed to fetch|NetworkError|Load failed/i.test(msg)) msg = "lỗi mạng";
        state.fetchError = msg;
        if (!state.data) showFatal("Lỗi khi tải " + DATA_URL + ": " + msg + ". Thử lại sau ít phút.");
      })
      .then(function () {
        btn.disabled = false;
        renderBanners();
      });
  }

  // ---------- wire up ----------
  function init() {
    updateThemeButton();
    $("theme-btn").addEventListener("click", function () {
      setTheme(effectiveTheme() === "dark" ? "light" : "dark");
    });
    if (window.matchMedia) {
      var mq = window.matchMedia("(prefers-color-scheme: dark)");
      var onChange = function () { updateThemeButton(); restyleCharts(); };
      if (mq.addEventListener) mq.addEventListener("change", onChange);
      else if (mq.addListener) mq.addListener(onChange);
    }
    $("refresh-btn").addEventListener("click", load);
    $("retry-btn").addEventListener("click", load);

    [["f-symbol", "symbol"], ["f-tf", "tf"], ["f-side", "side"]].forEach(function (p) {
      $(p[0]).addEventListener("change", function (e) {
        state.filters[p[1]] = e.target.value;
        if (state.data) renderSummary();
      });
    });

    document.querySelectorAll(".summary-table th[data-sort] button").forEach(function (b) {
      b.addEventListener("click", function () {
        var key = b.parentElement.dataset.sort;
        if (state.sort.key === key) state.sort.dir *= -1;
        else state.sort = { key: key, dir: 1 };
        if (state.data) renderSummary();
      });
    });

    var body = $("summary-body");
    body.addEventListener("click", function (e) {
      var tr = e.target.closest("tr");
      if (tr && tr.dataset.target) jumpToCard(tr.dataset.target);
    });
    body.addEventListener("keydown", function (e) {
      if (e.key !== "Enter") return;
      var tr = e.target.closest("tr");
      if (tr && tr.dataset.target) jumpToCard(tr.dataset.target);
    });

    load();
    setInterval(load, REFRESH_MS);
    setInterval(renderBanners, 30000);
    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState !== "visible" || !state.generatedAt) return;
      if (Date.now() - state.generatedAt.getTime() > REFRESH_MS) load();
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
