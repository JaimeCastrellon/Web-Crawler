// Polite schedule-page crawler for Sidearm Sports athletics sites, run in a browser tab that
// is already open on the target site (e.g. https://yalebulldogs.com/robots.txt), so every
// request is same-origin. Used for the 2026-11-16 crawl of Yale, Cornell and Penn.
//
// 1. Paste this file into the page's console (or a browser-automation JS tool).
// 2. ivyRobots()  -> check `blocked` is false and note `delay` (30 s on all Ivy sites).
// 3. ivyCrawl(seasons, patterns, delayMs) -> runs in the background; poll window.__ivy.
//    seasons: [2000, ..., 2026] minus 2020; patterns: ['{year}', '{year}-{next_yy}']
//    (Cornell: ['{year}-{next_yy}', '{year}']); delayMs: >= 1000 * robots Crawl-delay.
// 4. ivyDownload('yale') -> saves ivy_official_<school>.json, the input to
//    `python -m ivydata scores --official ...`.
//
// If a page comes back as an Imperva/Incapsula challenge (no schedule rows, "Incapsula" in
// the HTML), stop: the site does not allow automated access.

window.ivyRobots = function () {
  const lines = document.body.innerText.split('\n');
  let inStar = false, prevUA = false, delay = null; const dis = [];
  for (const raw of lines) {
    const m = raw.trim().match(/^([A-Za-z-]+)\s*:\s*(.*)$/); if (!m) continue;
    const k = m[1].toLowerCase(), v = m[2].trim();
    if (k === 'user-agent') { if (!prevUA) inStar = false; if (v === '*') inStar = true; prevUA = true; continue; }
    prevUA = false; if (!inStar) continue;
    if (k === 'crawl-delay') delay = parseFloat(v);
    if (k === 'disallow' && v) dis.push(v);
  }
  return { host: location.host, delay, blocked: dis.some(d => d === '/' || d.startsWith('/sports')) };
};

window.ivyParse = function (html) {
  const d = new DOMParser().parseFromString(html, 'text/html');
  const t = e => e ? e.textContent.replace(/\s+/g, ' ').trim() : '';
  return [...d.querySelectorAll('li.sidearm-schedule-game')].map(g => ({
    cls: g.className.replace(/\s+/g, ' '),
    gid: g.dataset.gameId || '',
    date: t(g.querySelector('.sidearm-schedule-game-opponent-date')),
    vs: t(g.querySelector('.sidearm-schedule-game-conference-vs')),
    opp: t(g.querySelector('.sidearm-schedule-game-opponent-name')),
    loc: t(g.querySelector('.sidearm-schedule-game-location')),
    res: t(g.querySelector('.sidearm-schedule-game-result')),
    conf: t(g.querySelector('.sidearm-schedule-game-conference-conference')),
    box: g.querySelector('.sidearm-schedule-game-links-boxscore a')?.getAttribute('href') || '',
  }));
};

window.ivyCrawl = function (seasons, patterns, delayMs) {
  const st = window.__ivy = { host: location.host, done: false, pages: [], started: Date.now(), delayMs };
  const sleep = ms => new Promise(z => setTimeout(z, ms));
  (async () => {
    let first = true;
    for (const y of seasons) {
      for (const p of patterns) {
        const slug = p.replace('{year}', y).replace('{next_yy}', String((y + 1) % 100).padStart(2, '0'));
        const url = '/sports/football/schedule/' + slug;
        if (!first) await sleep(delayMs);
        first = false;
        const rec = { season: y, slug, url, fetched_at: new Date().toISOString() };
        try {
          const r = await fetch(url); rec.status = r.status;
          if (r.ok) { const h = await r.text(); rec.bytes = h.length; rec.rows = ivyParse(h); } else rec.rows = [];
        } catch (e) { rec.status = 0; rec.error = String(e); rec.rows = []; }
        st.pages.push(rec);
        if (rec.rows.length > 0) break;
      }
    }
    st.done = true; st.finished = Date.now();
  })();
  return 'started';
};

window.ivyDownload = function (school) {
  const data = { exported_at: new Date().toISOString(), schools: { [school]: { host: location.host, pages: window.__ivy.pages } } };
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(data)], { type: 'application/json' }));
  a.download = `ivy_official_${school}.json`; document.body.appendChild(a); a.click();
};
