/* Small SVG bar charts. No library, so the charts also work offline. */
(function () {
  "use strict";
  var NS = "http://www.w3.org/2000/svg";

  function esc(t) {
    return String(t).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function niceMax(max) {
    if (max <= 4) return Math.max(max, 1);
    var pow = Math.pow(10, Math.floor(Math.log10(max)));
    var step = [1, 2, 2.5, 5, 10].find(function (s) { return s * pow >= max / 4; }) * pow;
    return Math.ceil(max / step) * step;
  }

  function ticks(top) {
    var n = top <= 4 ? top : 4, out = [];
    for (var i = 0; i <= n; i++) out.push((top * i) / n);
    return out;
  }

  function mount(el, svg, label) {
    el.innerHTML = svg.replace("<svg ", '<svg role="img" aria-label="' + esc(label) + '" ');
  }

  /* Vertical bars. data: {labels: [...], series: [{name, values: [...]}]} (series 1 = accent, 2 = amber) */
  function bars(el, data, label) {
    var W = 800, H = 300, L = 44, R = 12, T = 12, B = 58;
    var n = data.labels.length, k = data.series.length;
    var max = 0;
    data.series.forEach(function (s) { s.values.forEach(function (v) { if (v > max) max = v; }); });
    var top = niceMax(max);
    var pw = W - L - R, ph = H - T - B, group = pw / Math.max(n, 1);
    var bw = Math.min(40, (group * 0.74) / k);
    var out = ['<svg class="chart" viewBox="0 0 ' + W + " " + H + '" xmlns="' + NS + '">'];
    ticks(top).forEach(function (t) {
      var y = T + ph - (t / top) * ph;
      out.push('<line class="grid" x1="' + L + '" x2="' + (W - R) + '" y1="' + y + '" y2="' + y + '"/>');
      out.push('<text x="' + (L - 6) + '" y="' + (y + 4) + '" text-anchor="end">' + Math.round(t * 10) / 10 + "</text>");
    });
    out.push('<line class="axis" x1="' + L + '" x2="' + (W - R) + '" y1="' + (T + ph) + '" y2="' + (T + ph) + '"/>');
    var skip = Math.ceil(n / 14), showValues = n * k <= 28;
    data.labels.forEach(function (lab, i) {
      var cx = L + group * i + group / 2;
      data.series.forEach(function (s, j) {
        var v = s.values[i], h = (v / top) * ph;
        var x = cx - (bw * k) / 2 + bw * j, y = T + ph - h;
        out.push(
          '<rect class="' + (j === 0 ? "bar-a" : "bar-b") + '" x="' + x + '" y="' + y + '" width="' + (bw - 2) +
          '" height="' + h + '" rx="2"><title>' + esc(lab) + ", " + esc(s.name) + ": " + v + "</title></rect>"
        );
        if (showValues && v > 0)
          out.push('<text class="val" x="' + (x + (bw - 2) / 2) + '" y="' + (y - 4) + '" text-anchor="middle">' + v + "</text>");
      });
      if (i % skip === 0)
        out.push(
          '<text x="' + cx + '" y="' + (T + ph + 16) + '" text-anchor="' + (n > 8 ? "end" : "middle") + '"' +
          (n > 8 ? ' transform="rotate(-40 ' + cx + " " + (T + ph + 16) + ')"' : "") + ">" + esc(lab) + "</text>"
        );
    });
    out.push("</svg>");
    mount(el, out.join(""), label);
  }

  /* Horizontal bars. data: {labels: [...], values: [...]} */
  function hbars(el, data, label) {
    var n = data.labels.length, row = 28, L = 190, R = 56, T = 6;
    var W = 800, H = T + row * Math.max(n, 1) + 6;
    var max = Math.max.apply(null, data.values.concat([1]));
    var pw = W - L - R;
    var out = ['<svg class="chart" viewBox="0 0 ' + W + " " + H + '" xmlns="' + NS + '">'];
    data.labels.forEach(function (lab, i) {
      var y = T + row * i, w = (data.values[i] / max) * pw;
      var shown = lab.length > 30 ? lab.slice(0, 29) + "…" : lab;
      out.push('<text class="lbl" x="' + (L - 8) + '" y="' + (y + 18) + '" text-anchor="end"><title>' + esc(lab) + "</title>" + esc(shown) + "</text>");
      out.push('<rect class="bar-a" x="' + L + '" y="' + (y + 4) + '" width="' + w + '" height="' + (row - 10) + '" rx="2"><title>' + esc(lab) + ": " + data.values[i] + "</title></rect>");
      out.push('<text class="val" x="' + (L + w + 6) + '" y="' + (y + 18) + '">' + data.values[i] + "</text>");
    });
    out.push("</svg>");
    mount(el, out.join(""), label);
  }

  window.JWCharts = { bars: bars, hbars: hbars };
})();
