// Exports schedule/result rows from Wikipedia team-season articles via the MediaWiki API.
// Run in a tab open on https://en.wikipedia.org. Used for the 2026-11-16 export.
//
//   await wikiRun([['brown','Brown Bears'], ['columbia','Columbia Lions'], ['cornell','Cornell Big Red'],
//                  ['dartmouth','Dartmouth Big Green'], ['harvard','Harvard Crimson'], ['penn','Penn Quakers'],
//                  ['princeton','Princeton Tigers'], ['yale','Yale Bulldogs']], seasons)
//   wikiDownload()   // -> ivy_wikipedia_schedules.json, input to `python -m ivydata scores --wikipedia ...`
//
// Newer articles use {{CFB schedule entry}} templates (parsed to named fields here); older ones
// use positional {{CFB schedule}} rows, which are exported raw (`_raw`) and re-read in Python
// (ivydata.scores._positional_entry). Content is CC BY-SA 4.0; revision ids are recorded.

const UA = { 'Api-User-Agent': 'ivy-football-data/0.1 (https://github.com/JaimeCastrellon/Web-Crawler)' };

function strip(w) {
  return w.replace(/<!--[\s\S]*?-->/g, '').replace(/<ref[^>]*\/>/gi, '').replace(/<ref[\s\S]*?<\/ref>/gi, '');
}

function splitParams(s) {
  const out = []; let depth = 0, cur = '';
  for (let i = 0; i < s.length; i++) {
    const two = s.slice(i, i + 2);
    if (two === '{{' || two === '[[') { depth++; cur += two; i++; continue; }
    if (two === '}}' || two === ']]') { depth--; cur += two; i++; continue; }
    if (s[i] === '|' && depth === 0) { out.push(cur); cur = ''; continue; }
    cur += s[i];
  }
  out.push(cur); return out;
}

function templateBody(w, start) {
  let depth = 0, j = start;
  for (; j < w.length; j++) {
    if (w.startsWith('{{', j)) { depth++; j++; } else if (w.startsWith('}}', j)) { depth--; j++; if (depth === 0) break; }
  }
  return [w.slice(start + 2, j - 1), j];
}

function entries(w) {
  w = strip(w); const res = []; const re = /\{\{\s*CFB schedule entry/gi; let m;
  while ((m = re.exec(w))) {
    const [body, end] = templateBody(w, m.index); const p = {};
    for (const part of splitParams(body).slice(1)) {
      const k = part.indexOf('='); if (k < 0) continue;
      p[part.slice(0, k).trim().toLowerCase()] = part.slice(k + 1).trim();
    }
    res.push(p); re.lastIndex = end;
  }
  return res;
}

function positional(w) {
  w = strip(w); const m = /\{\{\s*CFB schedule\s*\n?\|/i.exec(w); if (!m) return [];
  const [body] = templateBody(w, m.index);
  const vals = splitParams(body).slice(1).map(v => v.trim()).filter(v => !/^[a-z_ ]+\s*=/.test(v));
  const dateRe = /^(Jan(uary)?|Feb(ruary)?|Aug(ust)?|Sep(t(ember)?)?|Oct(ober)?|Nov(ember)?|Dec(ember)?)\.?\s+\d{1,2}$/i;
  const rows = []; let cur = null;
  for (const v of vals) { if (dateRe.test(v)) { cur = [v]; rows.push(cur); } else if (cur) cur.push(v); }
  return rows.map(r => {
    const e = { date: r[0], _raw: r.join(' | '), _format: 'positional' };
    const res = r.find(x => /^[WLT]\s*\d+\s*[-–]\s*\d+/.test(x));
    if (res) {
      const mm = res.match(/^([WLT])\s*(\d+)\s*[-–]\s*(\d+)(.*)$/);
      e['w/l'] = mm[1].toLowerCase(); e.score = mm[2] + '–' + mm[3];
      const ot = (mm[4] || '').match(/(\d*)\s*OT/i); if (ot) e.ot = (ot[1] || '') + 'OT';
    }
    return e;
  });
}

window.wikiRun = async function (schoolTitles, seasons) {
  const st = window.__wiki = { done: false, pages: [], errors: [] };
  const titles = [];
  for (const [school, team] of schoolTitles) for (const y of seasons) titles.push({ school, season: y, title: `${y} ${team} football team` });
  for (let i = 0; i < titles.length; i += 40) {
    const chunk = titles.slice(i, i + 40);
    const u = '/w/api.php?action=query&prop=revisions&rvprop=content|ids&rvslots=main&format=json&formatversion=2&redirects=1&origin=*&titles='
      + encodeURIComponent(chunk.map(t => t.title).join('|'));
    try {
      const j = await (await fetch(u, { headers: UA })).json();
      const norm = Object.fromEntries((j.query.normalized || []).map(n => [n.from, n.to]));
      const red = Object.fromEntries((j.query.redirects || []).map(r => [r.from, r.to]));
      const byTitle = Object.fromEntries(j.query.pages.map(p => [p.title, p]));
      for (const t of chunk) {
        let tt = norm[t.title] || t.title; tt = red[tt] || tt; const pg = byTitle[tt];
        const rec = { school: t.school, season: t.season, title: tt, fetched_at: new Date().toISOString(),
          url: 'https://en.wikipedia.org/wiki/' + encodeURIComponent(tt.replace(/ /g, '_')) };
        if (!pg || pg.missing) { rec.exists = false; rec.entries = []; }
        else {
          const w = pg.revisions[0].slots.main.content; rec.exists = true; rec.revid = pg.revisions[0].revid;
          rec.entries = entries(w); if (!rec.entries.length) { rec.entries = positional(w); rec.format = 'positional'; }
        }
        st.pages.push(rec);
      }
    } catch (e) { st.errors.push(String(e)); }
    await new Promise(z => setTimeout(z, 1500));
  }
  st.done = true; return st;
};

window.wikiDownload = function () {
  const data = { exported_at: new Date().toISOString(), source: 'en.wikipedia.org (CC BY-SA 4.0)', pages: window.__wiki.pages };
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(data)], { type: 'application/json' }));
  a.download = 'ivy_wikipedia_schedules.json'; document.body.appendChild(a); a.click();
};
