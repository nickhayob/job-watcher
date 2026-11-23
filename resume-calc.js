/* Resume analysis, done entirely in the browser. The resume text never leaves the page.
 *
 * The history has each posting's title, employer and location (not its job
 * description), so a posting is matched on its title: which finance topics the
 * title names, what level it reads as, and whether the resume covers those topics.
 */
(function () {
  "use strict";

  /* id, label, regex for the resume text, regex for a posting title */
  var TOPICS = [
    ["fpa", "Financial planning and analysis",
      /fp\s*&\s*a|\bfpa\b|forecast|budget|variance|financial planning|financial analy/i,
      /fp\s*&\s*a|forecast|budget|planning|\bfinancial analyst|\bfinance analyst|\bfinancial\b/i],
    ["model", "Financial modeling",
      /financial model|\bdcf\b|discounted cash flow|\blbo\b|three[- ]statement|3[- ]statement|pro forma|sensitivity analysis/i,
      /model|valuation/i],
    ["valuation", "Valuation",
      /valuation|comparable compan|\bcomps\b|precedent transaction|appraisal/i,
      /valuation|appraisal/i],
    ["credit", "Credit and underwriting",
      /credit|underwrit|\bloans?\b|lending|risk rating|covenant/i,
      /credit|underwrit|\bloan|lending/i],
    ["treasury", "Treasury and cash management",
      /treasury|liquidity|cash management|cash flow forecast|working capital/i,
      /treasury|\bcash\b|liquidity/i],
    ["accounting", "Accounting and reporting",
      /accounting|\bgaap\b|reconcil|general ledger|month[- ]end|journal entr|\baudit|accounts (?:payable|receivable)|\bcpa\b/i,
      /account|audit|controller|\btax\b|billing|payable|receivable|reporting/i],
    ["invest", "Investments and markets",
      /investment|portfolio|equity research|securities|fixed income|asset management|bloomberg|capital iq|factset|stock pitch|hedge fund|private equity/i,
      /invest|portfolio|equity|securities|asset management|research|\bfund|trading|wealth|market/i],
    ["realestate", "Real estate",
      /real estate|\breit\b|property|multifamily|commercial real|land development|leasing/i,
      /real estate|property|\breit\b|\bland\b|development|lease|facilities/i],
    ["mna", "M&A and corporate development",
      /m\s*&\s*a\b|merger|acquisition|corporate development|due diligence|\bdeals?\b/i,
      /m\s*&\s*a\b|merger|acquisition|corporate development|\bdeal|strategy|strategic/i],
    ["data", "Data, analytics and reporting tools",
      /\bsql\b|\bpython\b|\bpandas\b|tableau|power\s?bi|looker|data analy|dashboard|visuali[sz]|regression|statistic/i,
      /\bdata\b|analytics|business intelligence|\bbi\b|insight|quant|statistic|reporting/i],
    ["risk", "Risk and controls",
      /\brisk\b|compliance|regulat|internal control|\bsox\b|stress test|basel/i,
      /\brisk\b|compliance|control|regulat|\bsox\b/i],
    ["pricing", "Pricing, revenue and business partnering",
      /pricing|revenue|commercial finance|business partner|margin|profitab|unit economics/i,
      /pricing|revenue|commercial|business partner|margin|\bsales\b/i],
    ["supply", "Supply chain and operations finance",
      /supply chain|procurement|sourcing|logistics|inventory|cost accounting/i,
      /supply|procure|sourcing|logistic|inventory|\bcost\b|operations/i],
  ];

  var TOOLS = [
    ["Excel", /\bexcel\b|vlookup|pivot table|\bvba\b/i],
    ["SQL", /\bsql\b/i],
    ["Python", /\bpython\b|\bpandas\b/i],
    ["Tableau / Power BI", /tableau|power\s?bi|looker/i],
    ["Bloomberg / Capital IQ / FactSet", /bloomberg|capital iq|factset/i],
    ["SAP / Oracle / NetSuite", /\bsap\b|\boracle\b|netsuite|hyperion|anaplan/i],
    ["PowerPoint", /powerpoint/i],
  ];

  var LEVELS = ["student", "entry", "mid", "senior"];
  var LEVEL_LABEL = { student: "Student or intern", entry: "Entry level (0-2 years)", mid: "Mid level (3-6 years)", senior: "Senior (7+ years)" };

  /* how well a posting's level fits the person's level, 0 to 1 */
  var FIT = {
    student: { intern: 1, entry: 1, standard: 0.6, senior: 0.1 },
    entry: { intern: 0.6, entry: 1, standard: 0.8, senior: 0.2 },
    mid: { intern: 0.1, entry: 0.6, standard: 1, senior: 0.7 },
    senior: { intern: 0, entry: 0.2, standard: 0.7, senior: 1 },
  };

  function topicsIn(text, which) {
    return TOPICS.filter(function (t) { return t[which].test(text); }).map(function (t) { return t[0]; });
  }
  function labelOf(id) { return TOPICS.filter(function (t) { return t[0] === id; })[0][1]; }

  function titleLevel(title) {
    if (/\bintern(?:ship)?\b|\bco-?op\b|summer analyst|apprentice/i.test(title)) return "intern";
    if (/\bsenior\b|\bsr\b\.?|principal|\bstaff\b|\blead\b|manager|director|\bvp\b|vice president|\bhead\b|chief|\bfellow\b|\bavp\b/i.test(title)) return "senior";
    if (/associate|analyst (?:i\b|1\b)|junior|entry|early career|graduate|new grad|rotational|development program|\bi\b$/i.test(title)) return "entry";
    return "standard";
  }

  function detectLevel(text) {
    var years = 0, m, re = /(\d{1,2})\s*\+?\s*(?:years|yrs)/gi;
    while ((m = re.exec(text))) years = Math.max(years, +m[1]);
    var student = /expected (?:graduation|to graduate)|anticipated graduation|candidate for|currently (?:pursuing|enrolled)|class of 20(?:2[5-9]|3\d)|\bintern\b|gpa/i.test(text);
    if (student && years < 3) return "student";
    if (years >= 7) return "senior";
    if (years >= 3) return "mid";
    return "entry";
  }

  function toolsIn(text) {
    return TOOLS.filter(function (t) { return t[1].test(text); }).map(function (t) { return t[0]; });
  }

  /* Plain checks on the resume text. ok = true is a pass. */
  function checks(text) {
    var lines = text.split(/\n/).map(function (l) { return l.trim(); }).filter(Boolean);
    var words = (text.match(/\S+/g) || []).length;
    var bullets = lines.filter(function (l) { return /^[•\-•●\*▪·–]/.test(l) || (l.split(/\s+/).length >= 8 && /[.;]$/.test(l)); });
    var withNumbers = bullets.filter(function (l) { return /\d|\$|%/.test(l); });
    var weak = (text.match(/responsible for|duties included|helped (?:with|to)|worked on|assisted with|participated in/gi) || []).length;
    var long = bullets.filter(function (l) { return l.split(/\s+/).length > 40; }).length;
    var out = [];
    out.push({ ok: words >= 250 && words <= 800, text: "Length: " + words + " words (about 300 to 700 fits one page well)." });
    out.push({ ok: /[\w.+-]+@[\w-]+\.[\w.]+/.test(text), text: /[\w.+-]+@[\w-]+\.[\w.]+/.test(text) ? "An email address is present." : "No email address found." });
    out.push({ ok: /\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}/.test(text), text: /\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}/.test(text) ? "A phone number is present." : "No phone number found." });
    var sections = ["education", "experience", "skills"].filter(function (s) { return new RegExp("^\\s*" + s, "im").test(text); });
    out.push({ ok: sections.length >= 2, text: "Sections found: " + (sections.length ? sections.join(", ") : "none of Education, Experience or Skills") + "." });
    var share = bullets.length ? Math.round((100 * withNumbers.length) / bullets.length) : 0;
    out.push({ ok: bullets.length === 0 || share >= 40, text: bullets.length ? share + "% of " + bullets.length + " bullet lines include a number, dollar amount or percent (aim for 40% or more)." : "No bullet lines detected." });
    out.push({ ok: weak === 0, text: weak ? weak + " weak phrase" + (weak === 1 ? "" : "s") + ' such as "responsible for" or "worked on"; start bullets with a strong verb instead.' : "No weak phrases like \"responsible for\"." });
    out.push({ ok: long === 0, text: long ? long + " bullet" + (long === 1 ? " is" : "s are") + " over 40 words; shorten them." : "No overly long bullets." });
    return out;
  }

  function levelFit(person, title) { return FIT[person][titleLevel(title)]; }

  /* Score one posting against a resume profile. Returns {score, matched, topics, level}. */
  function scorePosting(posting, profile, today) {
    var topics = topicsIn(posting.title, 3);
    var matched = topics.filter(function (t) { return profile.has.indexOf(t) !== -1; });
    var topicPart = topics.length ? (matched.length / topics.length) * 45 : 20;
    var rolePart = posting.in_role ? 20 : 0;
    var level = titleLevel(posting.title);
    var levelPart = FIT[profile.level][level] * 25;
    var freshPart = 0;
    if (today && posting.first_seen) {
      var age = Math.round((Date.parse(today) - Date.parse(posting.first_seen)) / 86400000);
      if (age <= 7 && !posting.first_run) freshPart = 10;
    }
    return {
      score: Math.round(topicPart + rolePart + levelPart + freshPart),
      matched: matched, topics: topics, level: level,
    };
  }

  /* postings: the open postings to consider. opts: {level, today, limit} */
  function analyze(text, postings, opts) {
    opts = opts || {};
    var has = topicsIn(text, 2);
    var profile = { has: has, level: opts.level || detectLevel(text) };
    var ranked = postings.map(function (p) {
      var s = scorePosting(p, profile, opts.today);
      return { posting: p, score: s.score, matched: s.matched, topics: s.topics, level: s.level };
    }).sort(function (a, b) {
      return b.score - a.score || (a.posting.first_seen < b.posting.first_seen ? 1 : -1) || a.posting.title.localeCompare(b.posting.title);
    });
    // how often each topic shows up in the titles being considered
    var demand = {};
    postings.forEach(function (p) { topicsIn(p.title, 3).forEach(function (t) { demand[t] = (demand[t] || 0) + 1; }); });
    var rows = Object.keys(demand).map(function (id) {
      return { id: id, label: labelOf(id), count: demand[id], has: has.indexOf(id) !== -1 };
    }).sort(function (a, b) { return b.count - a.count; });
    return {
      profile: profile,
      tools: toolsIn(text),
      topics: has.map(function (id) { return { id: id, label: labelOf(id) }; }),
      matches: ranked.slice(0, opts.limit || 25),
      considered: postings.length,
      gaps: rows.filter(function (r) { return !r.has; }).slice(0, 5),
      strengths: rows.filter(function (r) { return r.has; }).slice(0, 5),
      checks: checks(text),
    };
  }

  /* ---------- reading a .docx without a library ---------- */
  function xmlToText(xml) {
    return xml
      .replace(/<\/w:p>/g, "\n").replace(/<w:tab\/>/g, "\t").replace(/<w:br[^>]*\/>/g, "\n")
      .replace(/<[^>]+>/g, "")
      .replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&apos;/g, "'")
      .replace(/\n{3,}/g, "\n\n").trim();
  }

  function readDocx(file) {
    return file.arrayBuffer().then(function (ab) {
      var buf = new Uint8Array(ab), dv = new DataView(ab), eocd = -1, i;
      for (i = buf.length - 22; i >= Math.max(0, buf.length - 65557); i--) {
        if (dv.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
      }
      if (eocd < 0) throw new Error("This does not look like a .docx file.");
      var count = dv.getUint16(eocd + 10, true), p = dv.getUint32(eocd + 16, true);
      for (var n = 0; n < count; n++) {
        if (dv.getUint32(p, true) !== 0x02014b50) break;
        var method = dv.getUint16(p + 10, true), csize = dv.getUint32(p + 20, true);
        var nameLen = dv.getUint16(p + 28, true), extraLen = dv.getUint16(p + 30, true), commentLen = dv.getUint16(p + 32, true);
        var local = dv.getUint32(p + 42, true);
        var name = new TextDecoder().decode(buf.subarray(p + 46, p + 46 + nameLen));
        if (name === "word/document.xml") {
          var start = local + 30 + dv.getUint16(local + 26, true) + dv.getUint16(local + 28, true);
          var data = buf.subarray(start, start + csize);
          if (method === 0) return xmlToText(new TextDecoder().decode(data));
          if (typeof DecompressionStream === "undefined") throw new Error("This browser cannot open .docx files; paste the text instead.");
          var stream = new Blob([data]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
          return new Response(stream).text().then(xmlToText);
        }
        p += 46 + nameLen + extraLen + commentLen;
      }
      throw new Error("Could not find the text in this .docx file.");
    });
  }

  window.JWResume = {
    analyze: analyze, detectLevel: detectLevel, titleLevel: titleLevel, checks: checks,
    topicsIn: topicsIn, readDocx: readDocx, xmlToText: xmlToText, LEVELS: LEVELS, LEVEL_LABEL: LEVEL_LABEL,
  };
})();
