#!/usr/bin/env python3
"""Render data/latest.json into one self-contained page: web/index.html.

Images are inlined as data URIs (~1 MB in total), so the file works offline
and GitHub Pages serves it as a single document.
"""
import base64, datetime as dt, html, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "web")

MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
          "September", "Oktober", "November", "Dezember"]


def inline_images(offers):
    for o in offers:
        p = o.get("image_local")
        o["img"] = None
        if p and os.path.exists(os.path.join(WEB, p)):
            with open(os.path.join(WEB, p), "rb") as f:
                o["img"] = "data:image/webp;base64," + base64.b64encode(f.read()).decode()


def build():
    d = json.load(open(os.path.join(HERE, "data", "latest.json")))
    offers = d["offers"]
    inline_images(offers)
    slim = [{k: o.get(k) for k in ("id", "title", "kind", "category", "url", "until", "start", "added",
                                    "img", "text", "quota", "start_time", "receipt", "max_refund",
                                    "where", "sources")} for o in offers]
    gen = dt.datetime.fromisoformat(d["generated"])
    year, week = d["iso_week"].split("-W")
    stand = f"{gen.day}. {MONTHS[gen.month - 1]} {gen.year}, {gen:%H:%M} Uhr"

    src_html = "".join(
        f'<a class="src{"" if s["ok"] else " bad"}" href="{html.escape(s["url"])}" target="_blank" rel="noopener">'
        f'<span class="n">{html.escape(s["name"])}</span>'
        f'<span class="c">{s.get("kept", 0) if s["ok"] else "Fehler"}</span></a>'
        for s in d["sources"].values())

    page = TEMPLATE
    for k, v in {
        "__YEAR__": year, "__WEEK__": week, "__STAND__": stand,
        "__SOURCES__": src_html,
        "__DATA__": json.dumps({"offers": slim, "kinds": d["kinds"], "today": gen.date().isoformat()},
                               ensure_ascii=False).replace("</", "<\\/"),
    }.items():
        page = page.replace(k, v)
    os.makedirs(WEB, exist_ok=True)
    out = os.path.join(WEB, "index.html")
    with open(out + ".tmp", "w") as f:
        f.write(page)
    os.replace(out + ".tmp", out)
    print(f"web/index.html  {len(offers)} Aktionen, {os.path.getsize(out)/1e6:.1f} MB")


TEMPLATE = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gratis testen – KW __WEEK__</title>
<meta name="description" content="Alle laufenden Gratis-testen- und Geld-zurück-Aktionen in Deutschland, wöchentlich aktualisiert.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%230f7b52'/%3E%3Ctext x='16' y='23' font-family='Arial' font-weight='700' font-size='19' text-anchor='middle' fill='white'%3E0%E2%82%AC%3C/text%3E%3C/svg%3E">
<style>
:root{
  --paper:#eceee9; --sunk:#e0e3dc; --card:#ffffff; --ink:#15171c; --ink-2:#454b57;
  --ink-3:#6b7280; --line:#cdd2c8; --line-soft:#e1e5dc;
  --free:#0f7b52; --free-ink:#ffffff; --free-soft:#dcefe5;
  --part:#1f5fae; --part-soft:#dde8f6;
  --warn:#c8102e; --flash:#ffd400; --flash-ink:#15171c;
  --shadow:0 1px 0 rgba(21,23,28,.06), 0 6px 18px -12px rgba(21,23,28,.5);
  color-scheme:light;
}
@media (prefers-color-scheme:dark){ :root:not([data-theme="light"]){
  --paper:#0f1311; --sunk:#090c0a; --card:#181d1a; --ink:#e8ece9; --ink-2:#aab4ad;
  --ink-3:#7c877f; --line:#2b332e; --line-soft:#222924;
  --free:#3ecf96; --free-ink:#04140c; --free-soft:#163126;
  --part:#7fb2ff; --part-soft:#17263b; --warn:#ff5a6e;
  --shadow:0 1px 0 rgba(0,0,0,.4), 0 8px 22px -14px #000; color-scheme:dark;
}}
:root[data-theme="dark"]{
  --paper:#0f1311; --sunk:#090c0a; --card:#181d1a; --ink:#e8ece9; --ink-2:#aab4ad;
  --ink-3:#7c877f; --line:#2b332e; --line-soft:#222924;
  --free:#3ecf96; --free-ink:#04140c; --free-soft:#163126;
  --part:#7fb2ff; --part-soft:#17263b; --warn:#ff5a6e;
  --shadow:0 1px 0 rgba(0,0,0,.4), 0 8px 22px -14px #000; color-scheme:dark;
}
*{box-sizing:border-box;margin:0;padding:0}
html{-webkit-text-size-adjust:100%}
body{background:var(--paper);color:var(--ink);font:15px/1.45 "IBM Plex Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
a{color:inherit}
.wrap{max-width:1240px;margin:0 auto;padding:0 16px}
.cond{font-family:"Barlow Condensed","IBM Plex Sans",sans-serif}
.mono{font-family:"IBM Plex Mono",ui-monospace,monospace}

header{border-bottom:3px solid var(--ink);padding:26px 0 18px;background:var(--paper)}
.mast{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:12px 24px}
h1{font-family:"Barlow Condensed",sans-serif;font-weight:700;font-size:clamp(36px,5.6vw,58px);line-height:.9;letter-spacing:-.01em;text-transform:uppercase}
h1 .dot{color:var(--free)}
.tag{margin-top:8px;color:var(--ink-2);max-width:56ch}
.when{font-family:"IBM Plex Mono",monospace;font-size:11.5px;color:var(--ink-3);text-align:right;line-height:1.6}
.when b{color:var(--ink);font-weight:500}
.stats{display:flex;flex-wrap:wrap;gap:8px;margin-top:18px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:8px 12px;box-shadow:var(--shadow);min-width:120px}
.stat .v{font-family:"Barlow Condensed",sans-serif;font-weight:700;font-size:30px;line-height:1}
.stat .l{font-size:12px;color:var(--ink-3)}
.stat.free .v{color:var(--free)} .stat.soon .v{color:var(--warn)}
.srcs{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px;align-items:center}
.srcs .lbl{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--ink-3);margin-right:4px}
.src{display:inline-flex;gap:8px;align-items:baseline;text-decoration:none;border:1px solid var(--line);background:var(--card);border-radius:999px;padding:3px 10px;font-size:12.5px}
.src:hover{border-color:var(--ink-3)}
.src .c{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--ink-3)}
.src.bad .c{color:var(--warn)}

.bar{position:sticky;top:0;z-index:5;background:color-mix(in srgb,var(--paper) 92%,transparent);backdrop-filter:blur(8px);border-bottom:1px solid var(--line);padding:10px 0}
.row{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.row + .row{margin-top:8px}
input[type=search]{flex:1 1 220px;min-width:0;font:inherit;padding:8px 12px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--ink)}
select{font:inherit;font-size:13.5px;padding:8px 10px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--ink)}
.seg{display:flex;flex-wrap:wrap;gap:6px}
.pill{font:inherit;font-size:13px;cursor:pointer;border:1px solid var(--line);background:var(--card);color:var(--ink-2);border-radius:999px;padding:5px 11px;display:inline-flex;gap:6px;align-items:baseline}
.pill .n{font-family:"IBM Plex Mono",monospace;font-size:10.5px;color:var(--ink-3)}
.pill[aria-pressed="true"]{background:var(--ink);color:var(--paper);border-color:var(--ink)}
.pill[aria-pressed="true"] .n{color:inherit;opacity:.7}
.pill:focus-visible,select:focus-visible,input:focus-visible,.btn:focus-visible{outline:2px solid var(--free);outline-offset:2px}
.scroll{overflow-x:auto;scrollbar-width:none;flex-wrap:nowrap}
.scroll::-webkit-scrollbar{display:none}
.scroll .pill{white-space:nowrap;flex:none}

main{padding:22px 0 40px}
h2{font-family:"Barlow Condensed",sans-serif;font-weight:700;text-transform:uppercase;font-size:24px;letter-spacing:.01em;margin:6px 0 12px;display:flex;align-items:baseline;gap:10px}
h2 .n{font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--ink-3);font-weight:400;text-transform:none}
section + section{margin-top:30px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;box-shadow:var(--shadow);display:flex;flex-direction:column;overflow:hidden;position:relative}
.pic{aspect-ratio:16/10;background:#fff;display:flex;align-items:center;justify-content:center;border-bottom:1px solid var(--line-soft);position:relative;overflow:hidden}
.pic img{position:absolute;inset:0;width:100%;height:100%;object-fit:contain}
.pic .ph{font-family:"Barlow Condensed",sans-serif;font-weight:700;font-size:40px;color:#9aa39c;text-transform:uppercase;letter-spacing:.02em;text-align:center;padding:10px;line-height:1}
.badges{position:absolute;top:8px;left:8px;display:flex;gap:5px;flex-wrap:wrap}
.b{font-family:"Barlow Condensed",sans-serif;font-weight:700;text-transform:uppercase;font-size:13.5px;letter-spacing:.03em;line-height:1;padding:4px 7px 3px;border-radius:4px;background:var(--ink);color:#fff}
.b.gratis{background:var(--free);color:var(--free-ink)}
.b.teil{background:var(--part);color:#fff}
.b.probe{background:#7a4cc2;color:#fff}
.b.produkttest{background:#c26a12;color:#fff}
.b.garantie{background:#5b6470;color:#fff}
.b.neu{background:var(--flash);color:var(--flash-ink)}
.b.soon{background:var(--warn);color:#fff}
.body{padding:12px 14px 14px;display:flex;flex-direction:column;gap:7px;flex:1}
.cat{font-family:"IBM Plex Mono",monospace;font-size:10.5px;color:var(--ink-3);text-transform:uppercase;letter-spacing:.06em}
.card h3{font-size:16px;line-height:1.25;font-weight:600}
.due{font-size:13px;color:var(--ink-2);display:flex;flex-wrap:wrap;gap:4px 10px}
.due b{font-weight:600;color:var(--ink)}
.due .urg{color:var(--warn);font-weight:600}
.due .fut{color:var(--part);font-weight:600}
.facts{font-family:"IBM Plex Mono",monospace;font-size:11.5px;line-height:1.55;color:var(--ink-2);background:var(--sunk);border-radius:5px;padding:6px 8px}
.facts div{display:flex;gap:6px}
.facts span{color:var(--ink-3);flex:none}
.where{display:flex;flex-wrap:wrap;gap:4px}
.where span{font-size:11.5px;border:1px solid var(--line);border-radius:4px;padding:1px 6px;color:var(--ink-2)}
details{font-size:13px;color:var(--ink-2)}
details summary{cursor:pointer;color:var(--ink-3);font-size:12.5px;list-style:none}
details summary::-webkit-details-marker{display:none}
details summary::before{content:"＋ ";}
details[open] summary::before{content:"－ ";}
details p{white-space:pre-line;margin-top:6px}
.foot{margin-top:auto;padding-top:6px;display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap}
.btn{display:inline-flex;align-items:center;gap:6px;text-decoration:none;background:var(--free);color:var(--free-ink);font-weight:600;font-size:13.5px;border-radius:6px;padding:7px 12px}
.btn:hover{filter:brightness(1.08)}
.btn.off{background:var(--sunk);color:var(--ink-3)}
.via{font-size:11.5px;color:var(--ink-3)}
.via a{color:var(--ink-3)}
.empty{padding:40px 0;text-align:center;color:var(--ink-3)}

footer{border-top:3px solid var(--ink);padding:24px 0 40px;color:var(--ink-2);font-size:13.5px}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:22px}
footer h3{font-family:"Barlow Condensed",sans-serif;text-transform:uppercase;font-size:18px;color:var(--ink);margin-bottom:6px}
footer ol,footer ul{padding-left:18px}
footer li{margin:3px 0}
.legal{margin-top:20px;font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--ink-3)}
.theme{font:inherit;font-size:12px;border:1px solid var(--line);background:var(--card);color:var(--ink-2);border-radius:999px;padding:3px 10px;cursor:pointer;margin-top:6px}
@media (max-width:560px){
  .when{text-align:left}
  .stat{min-width:0;flex:1 1 40%}
  .grid{grid-template-columns:1fr}
}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <div class="mast">
      <div>
        <h1>Gratis<span class="dot">.</span>Testen</h1>
        <p class="tag">Alle laufenden Gratis-testen-, Geld-zurück- und Produktproben-Aktionen in Deutschland. Kaufen, Kassenbon hochladen, Geld zurück.</p>
      </div>
      <div class="when">Kalenderwoche <b>__YEAR__ / KW __WEEK__</b><br>Stand __STAND__<br>aktualisiert jeden Montag
        <br><button class="theme" id="theme" type="button">Hell/Dunkel</button></div>
    </div>
    <div class="stats" id="stats"></div>
    <div class="srcs"><span class="lbl">Quellen</span>__SOURCES__</div>
  </div>
</header>

<div class="bar">
  <div class="wrap">
    <div class="row">
      <input type="search" id="q" placeholder="Suchen: Marke, Produkt, Drogerie …" aria-label="Aktionen durchsuchen">
      <select id="sort" aria-label="Sortierung">
        <option value="due">Endet zuerst</option>
        <option value="new">Neueste zuerst</option>
        <option value="az">A–Z</option>
      </select>
    </div>
    <div class="row seg scroll" id="kinds" role="group" aria-label="Art der Aktion"></div>
    <div class="row seg scroll" id="cats" role="group" aria-label="Kategorie"></div>
  </div>
</div>

<main class="wrap" id="main"></main>

<footer>
  <div class="wrap cols">
    <div>
      <h3>So funktioniert's</h3>
      <ol>
        <li>Aktionsprodukt im Aktionszeitraum kaufen – oft nur bestimmte Packungen oder Händler.</li>
        <li>Kassenbon fotografieren und auf der Aktionsseite hochladen, IBAN angeben.</li>
        <li>Erstattung kommt meist innerhalb von 2–6 Wochen aufs Konto.</li>
      </ol>
    </div>
    <div>
      <h3>Tipps</h3>
      <ul>
        <li>Pro Aktion einen eigenen Kassenbon – Aktionsartikel getrennt bezahlen.</li>
        <li>Tageskontingente sind oft morgens nach wenigen Minuten weg: Startzeit beachten.</li>
        <li>Original-Bon bis zur Auszahlung aufbewahren.</li>
        <li>Meist gilt: eine Teilnahme pro Person, Haushalt und IBAN.</li>
      </ul>
    </div>
    <div>
      <h3>Die Arten</h3>
      <ul>
        <li><b>100 % zurück</b> – voller Kaufpreis, ggf. bis zu einem Höchstbetrag.</li>
        <li><b>Teil-Cashback</b> – ein fester Betrag oder Anteil zurück.</li>
        <li><b>Gratisprobe</b> – kostenlos bestellen, nichts kaufen.</li>
        <li><b>Produkttest</b> – bewerben (z. B. REWE, dm), Auswahl durch den Händler.</li>
        <li><b>Geld-zurück-Garantie</b> – Erstattung nur, wenn du nicht zufrieden bist.</li>
      </ul>
    </div>
  </div>
  <div class="wrap legal">Alle Angaben ohne Gewähr. Zusammengestellt aus Sparwelt, DealDoktor, DailyDeal, Geldschnurrbart und der mydealz-Community-Liste. Es gelten die Teilnahmebedingungen der jeweiligen Aktion – Kontingente können vorzeitig erschöpft sein.</div>
</footer>

<script id="data" type="application/json">__DATA__</script>
<script>
(function(){
const D = JSON.parse(document.getElementById('data').textContent);
const KINDS = D.kinds, TODAY = new Date(D.today + 'T00:00:00');
const KIND_ORDER = ['gratis','teil','probe','produkttest','garantie'];
const $ = s => document.querySelector(s);
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const day = iso => iso ? new Date(iso + 'T00:00:00') : null;
const daysTo = iso => iso ? Math.round((day(iso) - TODAY) / 864e5) : null;
const fmt = iso => { const d = day(iso); return d ? d.toLocaleDateString('de-DE', {day:'2-digit', month:'2-digit', year: d.getFullYear() === TODAY.getFullYear() ? undefined : 'numeric'}) : ''; };
const isNew = o => o.added && (TODAY - day(o.added)) / 864e5 <= 7;
const soon = o => o.until && daysTo(o.until) <= 7;

let state = {q:'', kind:'all', cat:'all', sort:'due'};
try { Object.assign(state, JSON.parse(localStorage.getItem('gt-state') || '{}'), {q:''}); } catch(e) {}
const save = () => { try { localStorage.setItem('gt-state', JSON.stringify({kind:state.kind, cat:state.cat, sort:state.sort})); } catch(e) {} };

// header stats
const all = D.offers;
const nFree = all.filter(o => o.kind === 'gratis').length;
$('#stats').innerHTML = [
  ['', all.length, 'Aktionen laufen'],
  ['free', nFree, '× 100 % Geld zurück'],
  ['', all.filter(isNew).length, 'neu in den letzten 7 Tagen'],
  ['soon', all.filter(soon).length, 'enden in ≤ 7 Tagen'],
].map(([c,v,l]) => `<div class="stat ${c}"><div class="v">${v}</div><div class="l">${l}</div></div>`).join('');

function pills(el, items, key){
  el.innerHTML = items.map(([v,l,n]) => `<button type="button" class="pill" data-v="${esc(v)}" aria-pressed="${state[key]===v}">${esc(l)} <span class="n">${n}</span></button>`).join('');
  el.onclick = e => { const b = e.target.closest('.pill'); if (!b) return; state[key] = b.dataset.v; save(); render(); };
}

function matches(o, ignore){
  if (ignore !== 'kind' && state.kind !== 'all' && o.kind !== state.kind) return false;
  if (ignore !== 'cat' && state.cat !== 'all' && o.category !== state.cat) return false;
  if (state.q){
    const hay = (o.title + ' ' + o.category + ' ' + (o.text||'') + ' ' + (o.where||'')).toLowerCase();
    if (!state.q.toLowerCase().split(/\s+/).every(w => hay.includes(w))) return false;
  }
  return true;
}

function card(o){
  const d = daysTo(o.until), st = daysTo(o.start);
  const badges = [`<span class="b ${o.kind}">${esc(KINDS[o.kind])}</span>`];
  if (isNew(o)) badges.push('<span class="b neu">Neu</span>');
  if (o.until && d <= 3) badges.push(`<span class="b soon">${d <= 0 ? 'Letzter Tag' : 'Noch ' + d + (d === 1 ? ' Tag' : ' Tage')}</span>`);
  const pic = o.img ? `<img src="${o.img}" alt="" loading="lazy">`
                    : `<div class="ph">${esc(o.title.split(/[\s–-]+/).slice(0,2).join(' '))}</div>`;
  const due = [];
  if (st != null && st > 0) due.push(`<span class="fut">startet ${fmt(o.start)}</span>`);
  if (o.until) due.push(`bis <b>${fmt(o.until)}</b>` + (d > 3 ? ` <span>· noch ${d} Tage</span>` : (d >= 0 ? ` <span class="urg">· ${d === 0 ? 'heute' : 'noch ' + d + (d === 1 ? ' Tag' : ' Tage')}</span>` : '')));
  else due.push('<span>ohne festes Enddatum</span>');
  const facts = [];
  if (o.quota) facts.push(['Kontingent', o.quota]);
  if (o.start_time) facts.push(['Start', o.start_time]);
  if (o.max_refund) facts.push(['max.', o.max_refund]);
  if (o.receipt) facts.push(['Beleg', o.receipt]);
  const where = (o.where || '').split(/,\s*/).filter(Boolean);
  const via = o.sources.map(s => `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.name)}</a>`).join(', ');
  return `<article class="card">
    <div class="pic">${pic}<div class="badges">${badges.join('')}</div></div>
    <div class="body">
      <div class="cat">${esc(o.category)}</div>
      <h3>${esc(o.title)}</h3>
      <div class="due">${due.join('')}</div>
      ${where.length ? `<div class="where">${where.map(w => `<span>${esc(w)}</span>`).join('')}</div>` : ''}
      ${facts.length ? `<div class="facts">${facts.map(([k,v]) => `<div><span>${k}</span>${esc(v)}</div>`).join('')}</div>` : ''}
      ${o.text ? `<details><summary>Details</summary><p>${esc(o.text)}</p></details>` : ''}
      <div class="foot">
        ${o.url ? `<a class="btn" href="${esc(o.url)}" target="_blank" rel="noopener">Zur Aktion →</a>` : `<span class="btn off">kein Direktlink</span>`}
        <span class="via">via ${via}</span>
      </div>
    </div>
  </article>`;
}

function sorted(list){
  const by = {
    due: (a,b) => (a.until||'9999').localeCompare(b.until||'9999') || a.title.localeCompare(b.title,'de'),
    new: (a,b) => (b.added||'').localeCompare(a.added||'') || a.title.localeCompare(b.title,'de'),
    az:  (a,b) => a.title.localeCompare(b.title,'de'),
  }[state.sort];
  return list.slice().sort(by);
}

function render(){
  const kc = {}, cc = {};
  all.filter(o => matches(o,'kind')).forEach(o => kc[o.kind] = (kc[o.kind]||0) + 1);
  all.filter(o => matches(o,'cat')).forEach(o => cc[o.category] = (cc[o.category]||0) + 1);
  const totalK = Object.values(kc).reduce((a,b)=>a+b,0), totalC = Object.values(cc).reduce((a,b)=>a+b,0);
  pills($('#kinds'), [['all','Alle Arten',totalK], ...KIND_ORDER.filter(k => kc[k]).map(k => [k, KINDS[k], kc[k]])], 'kind');
  const cats = [...new Set(all.map(o => o.category))].sort((a,b) => (cc[b]||0) - (cc[a]||0));
  pills($('#cats'), [['all','Alle Kategorien',totalC], ...cats.filter(c => cc[c]).map(c => [c, c, cc[c]])], 'cat');
  $('#sort').value = state.sort;

  const list = sorted(all.filter(o => matches(o)));
  if (!list.length){ $('#main').innerHTML = '<div class="empty">Keine Aktion passt zu diesen Filtern.</div>'; return; }
  let html = '';
  if (state.sort === 'due' && state.kind === 'all'){
    // the headline case: full refunds first, everything else after
    const groups = KIND_ORDER.map(k => [k, list.filter(o => o.kind === k)]).filter(([,l]) => l.length);
    const head = {gratis:'100 % Geld zurück', teil:'Teil-Cashback', probe:'Gratisproben', produkttest:'Produkttests', garantie:'Geld-zurück-Garantie'};
    html = groups.map(([k,l]) => `<section><h2>${head[k]} <span class="n">${l.length}</span></h2><div class="grid">${l.map(card).join('')}</div></section>`).join('');
  } else {
    html = `<section><div class="grid">${list.map(card).join('')}</div></section>`;
  }
  $('#main').innerHTML = html;
}

$('#q').addEventListener('input', e => { state.q = e.target.value.trim(); render(); });
$('#sort').addEventListener('change', e => { state.sort = e.target.value; save(); render(); });
if (!KINDS[state.kind] && state.kind !== 'all') state.kind = 'all';
render();

const root = document.documentElement;
try { const t = localStorage.getItem('gt-theme'); if (t) root.dataset.theme = t; } catch(e) {}
$('#theme').onclick = () => {
  const dark = root.dataset.theme ? root.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
  root.dataset.theme = dark ? 'light' : 'dark';
  try { localStorage.setItem('gt-theme', root.dataset.theme); } catch(e) {}
};
})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    build()
