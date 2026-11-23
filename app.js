/* Shared code for all three pages: navigation, data loading, the shortlist. */
(function () {
  "use strict";
  var JW = {};

  JW.PAGES = [
    ["index.html", "Today"],
    ["browse.html", "Browse"],
    ["market.html", "Market"],
  ];

  JW.esc = function (text) {
    return String(text == null ? "" : text).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };

  /* The one navigation bar, drawn into <div id="nav"> on every page. */
  JW.renderNav = function (active) {
    var tabs = JW.PAGES.map(function (p) {
      var current = p[0] === active ? ' aria-current="page"' : "";
      return '<a class="tab" href="' + p[0] + '"' + current + ">" + p[1] + "</a>";
    }).join("");
    document.getElementById("nav").innerHTML =
      '<nav class="nav" aria-label="Main"><div class="nav-inner">' +
      '<a class="brand" href="index.html">Job Watcher</a>' + tabs + "</div></nav>";
  };

  /* CSV with quoted fields, doubled quotes and line breaks inside quotes. */
  JW.parseCSV = function (text) {
    var rows = [], row = [], field = "", inQuotes = false, i = 0, c;
    if (text.charCodeAt(0) === 0xfeff) text = text.slice(1);
    while (i < text.length) {
      c = text[i];
      if (inQuotes) {
        if (c === '"') {
          if (text[i + 1] === '"') { field += '"'; i++; }
          else inQuotes = false;
        } else field += c;
      } else if (c === '"') inQuotes = true;
      else if (c === ",") { row.push(field); field = ""; }
      else if (c === "\n" || c === "\r") {
        if (c === "\r" && text[i + 1] === "\n") i++;
        row.push(field); field = "";
        rows.push(row); row = [];
      } else field += c;
      i++;
    }
    if (field !== "" || row.length) { row.push(field); rows.push(row); }
    var header = rows.shift() || [];
    return rows.filter(function (r) { return r.length > 1 || r[0] !== ""; }).map(function (r) {
      var o = {};
      header.forEach(function (h, k) { o[h] = r[k] === undefined ? "" : r[k]; });
      return o;
    });
  };

  JW.getJSON = function (url) {
    return fetch(url, { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error(url + " returned " + r.status);
      return r.json();
    });
  };

  JW.getHistory = function () {
    return fetch("data/history.csv", { cache: "no-cache" })
      .then(function (r) {
        if (!r.ok) throw new Error("data/history.csv returned " + r.status);
        return r.text();
      })
      .then(function (text) {
        return JW.parseCSV(text).map(function (r) {
          r.in_role = r.in_role === "true";
          r.first_run = r.first_run === "true";
          return r;
        });
      });
  };

  /* Both data files, plus the date of the latest run. */
  JW.loadData = function () {
    return Promise.all([JW.getJSON("data/status.json"), JW.getHistory()]).then(function (a) {
      return { status: a[0], rows: a[1], runDate: String(a[0].run_time).slice(0, 10) };
    });
  };

  JW.dayNumber = function (iso) {
    var p = iso.split("-");
    return Math.round(Date.UTC(+p[0], +p[1] - 1, +p[2]) / 86400000);
  };
  JW.daysBetween = function (from, to) { return JW.dayNumber(to) - JW.dayNumber(from); };

  JW.formatRunTime = function (iso) {
    var d = new Date(iso);
    if (isNaN(d)) return iso;
    return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) +
      " (" + iso.replace("T", " ").replace("Z", " UTC") + ")";
  };

  /* ---------- the shortlist, kept in this browser ---------- */
  var KEY = "jobwatcher.shortlist";
  JW.shortlist = {
    ids: function () {
      try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch (e) { return []; }
    },
    has: function (id) { return JW.shortlist.ids().indexOf(id) !== -1; },
    toggle: function (id) {
      var ids = JW.shortlist.ids(), at = ids.indexOf(id);
      if (at === -1) ids.push(id); else ids.splice(at, 1);
      try { localStorage.setItem(KEY, JSON.stringify(ids)); } catch (e) { /* storage blocked */ }
      return at === -1;
    },
  };

  /* ---------- offline notice and service worker ---------- */
  JW.watchConnection = function () {
    var banner = document.getElementById("offline");
    if (!banner) return;
    function update() { banner.hidden = navigator.onLine !== false; }
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    update();
  };

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("sw.js").catch(function () { /* the site still works without it */ });
    });
  }

  window.JW = JW;
})();
