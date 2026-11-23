/* Every number on the Market page, computed from the history rows.
 *
 * rows: the parsed history.csv (in_role and first_run are booleans).
 * lastRun: the date of the latest run, YYYY-MM-DD.
 *
 * Postings with first_run = true were already open when the tool began
 * watching their source, so their start date is unknown and the definitions
 * that need a start date leave them out.
 */
(function () {
  "use strict";

  function dayNumber(iso) {
    var p = iso.split("-");
    return Math.round(Date.UTC(+p[0], +p[1] - 1, +p[2]) / 86400000);
  }
  function isoFromDay(n) { return new Date(n * 86400000).toISOString().slice(0, 10); }

  function countBy(rows, keyFn) {
    var m = {};
    rows.forEach(function (r) {
      var k = keyFn(r);
      if (k !== "" && k != null) m[k] = (m[k] || 0) + 1;
    });
    return m;
  }

  function sortedEntries(map) {
    return Object.keys(map)
      .map(function (k) { return [k, map[k]]; })
      .sort(function (a, b) { return b[1] - a[1] || (a[0] < b[0] ? -1 : 1); });
  }

  function median(values) {
    if (!values.length) return null;
    var s = values.slice().sort(function (a, b) { return a - b; });
    var mid = Math.floor(s.length / 2);
    return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
  }

  var BUCKETS = [
    ["0", 0, 0], ["1", 1, 1], ["2", 2, 2], ["3-4", 3, 4],
    ["5-7", 5, 7], ["8-14", 8, 14], ["15-30", 15, 30], ["31+", 31, Infinity],
  ];

  function compute(rows, lastRun) {
    var open = rows.filter(function (r) { return r.status === "open"; });

    /* 1 and 2: per-day counts on one shared date axis */
    var first = lastRun;
    rows.forEach(function (r) { if (r.first_seen && r.first_seen < first) first = r.first_seen; });
    var dates = [];
    for (var d = dayNumber(first); d <= dayNumber(lastRun); d++) dates.push(isoFromDay(d));
    var notFirstRun = rows.filter(function (r) { return !r.first_run; });
    var newAll = countBy(notFirstRun, function (r) { return r.first_seen; });
    var newRole = countBy(notFirstRun.filter(function (r) { return r.in_role; }), function (r) { return r.first_seen; });
    var removed = countBy(rows, function (r) { return r.removed_date; });
    function series(m) { return dates.map(function (x) { return m[x] || 0; }); }

    /* 3: open postings per employer */
    var perEmployer = sortedEntries(countBy(open, function (r) { return r.employer; }));

    /* 4: days open, for removed postings that are not first-run postings */
    var closed = notFirstRun.filter(function (r) { return r.removed_date !== ""; });
    var daysOpen = closed.map(function (r) { return dayNumber(r.removed_date) - dayNumber(r.first_seen); });
    var histogram = BUCKETS.map(function (b) {
      return daysOpen.filter(function (v) { return v >= b[1] && v <= b[2]; }).length;
    });

    /* 5: share removed within seven days, among postings first seen at least seven days before the last run */
    var cutoff = isoFromDay(dayNumber(lastRun) - 7);
    var eligible = notFirstRun.filter(function (r) { return r.first_seen <= cutoff; });
    var quick = eligible.filter(function (r) {
      return r.removed_date !== "" && dayNumber(r.removed_date) - dayNumber(r.first_seen) <= 7;
    });

    /* 6: top locations among open postings */
    var locations = sortedEntries(countBy(open, function (r) { return r.location; }));

    return {
      dates: dates,
      newAll: series(newAll),
      newRole: series(newRole),
      removedPerDay: series(removed),
      perEmployer: perEmployer,
      openTotal: open.length,
      daysOpen: daysOpen,
      daysOpenMedian: median(daysOpen),
      bucketLabels: BUCKETS.map(function (b) { return b[0]; }),
      histogram: histogram,
      shareDenominator: eligible.length,
      shareNumerator: quick.length,
      shareRemovedWithin7: eligible.length ? quick.length / eligible.length : null,
      topLocations: locations.slice(0, 15),
    };
  }

  window.JWMarket = { compute: compute, median: median };
})();
