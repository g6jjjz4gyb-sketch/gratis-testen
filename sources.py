"""Readers for every source of German "gratis testen" / Geld-zurück offers.

Each reader returns a list of raw offers in one shared shape (see `offer()`);
run.py merges them, so a reader only reports what its source actually says.
None of these sites need a browser: Sparwelt ships its data as Nuxt JSON,
DailyDeal has an open WordPress API, the rest is plain HTML or a public sheet.
"""
import csv, datetime as dt, html, io, json, re, subprocess, time
import urllib.parse, urllib.request

from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")
TODAY = dt.date.today()

SOURCES = {
    "sparwelt":   {"name": "Sparwelt",         "url": "https://www.sparwelt.de/gratis/cashback"},
    "dealdoktor": {"name": "DealDoktor",       "url": "https://www.dealdoktor.de/gratis-testen/"},
    "dailydeal":  {"name": "DailyDeal",        "url": "https://www.dailydeal.de/waschmittel-gratis-testen/"},
    "geldschnurrbart": {"name": "Geldschnurrbart",
                        "url": "https://geldschnurrbart.de/geld-sparen/gratis-testen/"},
    "sheet":      {"name": "mydealz-Liste",
                   "url": "https://docs.google.com/spreadsheets/d/"
                          "1wcqckNai9SyRbQLt-pj6FHzGM7sypoET9glyAE05u2E/htmlview"},
}


# --------------------------------------------------------------------- HTTP

def get(url, tries=3, timeout=30, head_only=False):
    """GET a page and return (final_url, text). Falls back to curl, whose TLS
    stack some CDNs accept where Python's is refused."""
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9",
                "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"},
                method="HEAD" if head_only else "GET")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = b"" if head_only else r.read()
                cs = r.headers.get_content_charset() or "utf-8"
                return r.geturl(), body.decode(cs, "replace")
        except Exception as e:
            last = e
            time.sleep(1 + i)
    try:
        out = subprocess.run(
            ["curl", "-sL", "--compressed", "--max-time", str(timeout), "-A", UA,
             "-H", "Accept-Language: de-DE", "-w", "\n%{url_effective}", url],
            capture_output=True, timeout=timeout + 10)
        if out.returncode == 0 and out.stdout:
            body, _, final = out.stdout.decode("utf-8", "replace").rpartition("\n")
            return final.strip(), body
    except Exception as e:
        last = e
    raise RuntimeError(f"{url}: {last}")


def resolve(url):
    """Follow redirects (affiliate /goto/ links) to the real campaign page."""
    try:
        final, _ = get(url, tries=2, timeout=20, head_only=True)
    except Exception:
        try:
            final, _ = get(url, tries=1, timeout=20)
        except Exception:
            return url
    return final


def og_image(page_html):
    m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', page_html) \
        or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', page_html)
    return html.unescape(m.group(1)) if m else None


# ------------------------------------------------------------------ helpers

def offer(source, title, **kw):
    """The shared raw-offer shape. Unknown fields stay None."""
    o = dict(source=source, title=clean(title), url=None, source_url=None,
             image=None, until=None, start=None, kind=None, category=None,
             text=None, quota=None, start_time=None, receipt=None, where=None,
             added=None, max_refund=None)
    o.update({k: v for k, v in kw.items() if v not in ("", None)})
    return o


def clean(s):
    s = html.unescape(s or "")
    s = re.sub(r"\s+", " ", s).strip(" -–:|")
    return s


def strip_tracking(url):
    if not url:
        return url
    p = urllib.parse.urlsplit(url)
    q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query)
         if not re.match(r"(utm_|sv1|sv_|gclid|fbclid|ref|affiliate|awc|subid)", k, re.I)]
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, urllib.parse.urlencode(q), p.fragment))


DATE_RE = re.compile(r"\b(\d{1,2})\.\s?(\d{1,2})\.(\d{4}|\d{2})?\b")


def parse_date(s, default_year=None):
    """'15.12.2026', '8.11.2026', '12.10.' -> date. None if not a date."""
    if not s:
        return None
    m = DATE_RE.search(s)
    if not m:
        m2 = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
        if m2:
            return dt.date(int(m2[1]), int(m2[2]), int(m2[3]))
        return None
    d, mo, y = int(m[1]), int(m[2]), m[3]
    if y is None:
        y = default_year or TODAY.year
    y = int(y)
    if y < 100:
        y += 2000
    try:
        return dt.date(y, mo, d)
    except ValueError:
        return None


def all_dates(text, default_year=None):
    out = []
    for m in DATE_RE.finditer(text or ""):
        d = parse_date(m.group(0), default_year)
        if d and 2020 < d.year < 2100:
            out.append(d)
    return out


def iso(d):
    return d.isoformat() if d else None


# ----------------------------------------------------------------- Sparwelt

def sparwelt():
    """Nuxt payload of /gratis/cashback: every deal with description, campaign
    link (affiliateUrl), image and its publication window."""
    _, page = get(SOURCES["sparwelt"]["url"])
    soup = BeautifulSoup(page, "lxml")
    data = json.loads(soup.find(id="__NUXT_DATA__").string)

    def res(i, depth=0):
        v = data[i]
        if isinstance(v, dict):
            return {k: res(x, depth + 1) for k, x in v.items()} if depth < 6 else None
        if isinstance(v, list):
            if v and v[0] in ("ShallowReactive", "Reactive", "Ref", "ShallowRef"):
                return res(v[1], depth)
            return [res(x, depth + 1) for x in v] if depth < 6 else None
        return v

    out, seen = [], set()
    for i, v in enumerate(data):
        if not (isinstance(v, dict) and "affiliateUrl" in v and "publication" in v):
            continue
        d = res(i)
        if d["id"] in seen:
            continue
        seen.add(d["id"])
        desc = d.get("description") or ""
        desc = re.sub(r"_?Bild kann mit KI erstellt oder modifiziert worden sein\._?", "", desc)
        pub = d.get("publication") or {}
        img = (d.get("image") or {}).get("url")
        until = (pub.get("till") or "")[:10] or None
        start = (pub.get("from") or "")[:10] or None
        # publication.till is the listing window; the text names the real dates
        m = re.search(r"Aktionszeitraum[^:]*:\s*\**\s*([\d.]+)\s*bis\s*([\d.]+)", desc)
        if m:
            start = iso(parse_date(m[1])) or start
            until = iso(parse_date(m[2])) or until
        maxr = re.search(r"maximale Rückerstattung beträgt\s*([\d,]+\s*€)", desc)
        out.append(offer(
            "sparwelt", d["title"],
            url=strip_tracking(d.get("affiliateUrl")),
            source_url=SOURCES["sparwelt"]["url"] + f"#deal-{d['id']}",
            image=("https://sparwelt-cdn-assets.imgix.net/" + img + "?auto=format&w=640") if img else None,
            until=until, start=start, text=md_to_text(desc),
            added=(d.get("publishedAt") or "")[:10] or None,
            max_refund=maxr[1].replace(" ", "") if maxr else None,
        ))
    return out


def md_to_text(md):
    md = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", md)
    md = md.replace("**", "").replace("_", " ")
    lines = [l.strip(" -*") for l in md.splitlines()]
    return "\n".join(l for l in lines if l and l not in ("Teilnahmebedingungen",))


# --------------------------------------------------------------- DealDoktor

DD_CATEGORY = {
    "Lebensmittel": "Lebensmittel", "Pflege": "Drogerie & Pflege",
    "Haushalt": "Haushalt", "Tier": "Tierbedarf",
}


def dealdoktor():
    """The curated overview list: one <li> per campaign under a category <h2>,
    each linking to a deal page that carries the image and the campaign link."""
    _, page = get(SOURCES["dealdoktor"]["url"])
    soup = BeautifulSoup(page, "html.parser")
    out = []
    for h2 in soup.find_all("h2"):
        sec = h2.get_text(" ", strip=True)
        if re.search(r"Gewinnspiel|ALDI|Tipps|FAQ", sec):
            continue
        ul = h2.find_next_sibling("ul")
        if not ul:
            continue
        cat = next((v for k, v in DD_CATEGORY.items() if k in sec), None)
        rewe = "REWE" in sec
        for li in ul.find_all("li", recursive=False):
            text = li.get_text(" ", strip=True)
            a = li.find("a")
            if not a or not text.upper().startswith("GRATIS"):
                continue
            name = clean(a.get_text())
            paren = re.search(r"\(([^)]*)\)", text[text.find(name) + len(name):] if name in text else text)
            info = paren[1] if paren else ""
            until = start = None
            m = re.search(r"bis\s+([\d.]+)", info)
            if m:
                ends = all_dates(m[0])
                until = iso(ends[0]) if ends else None
            m = re.search(r"ab\s+([\d.]+)", info)
            if m:
                year = parse_date(until).year if until else None
                start = iso(parse_date(m[1], year))
            notes = [n.strip(" *") for n in re.split(r",", info)
                     if n.strip() and not re.search(r"\bbis\b|\bab\b|Ankündigung|kein Datum", n)]
            kind = "produkttest" if rewe else ("probe" if re.search(r"Gratisprobe", info) else None)
            out.append(offer(
                "dealdoktor", name, source_url=a["href"], until=until, start=start,
                category=cat, kind=kind, where=", ".join(notes) or None,
                added=iso(TODAY) if "*NEU*" in text else None,
                text=f"REWE-Produkttest: Bewerbung über die REWE-App bzw. rewe.de" if rewe else None,
            ))
    # Deal pages: image + where "Zum Deal" leads. REWE tests all share one page.
    cache = {}
    for o in out:
        link = o["source_url"]
        if link not in cache:
            try:
                final, p = get(link, tries=2)
                goto = re.search(r'href="(https://www\.dealdoktor\.de/goto/deal/\d+/?)"', p)
                desc = re.search(r'<meta property="og:description" content="([^"]*)"', p)
                img = og_image(p) if "/goto/" not in link else None
                if img and "DD-Open-Graph" in img:      # site-wide default, not the product
                    img = None
                cache[link] = dict(
                    image=img,
                    url=strip_tracking(resolve(goto[1])) if goto else None,
                    desc=html.unescape(desc[1]) if desc else None)
                time.sleep(0.3)
            except Exception:
                cache[link] = {}
        c = cache[link]
        if "/goto/" in link:              # links straight to the campaign
            o["url"] = strip_tracking(resolve(link))
            o["source_url"] = SOURCES["dealdoktor"]["url"]
        else:
            o["url"] = c.get("url")
            o["image"] = c.get("image")
            o["text"] = o["text"] or c.get("desc")
    return out


# ---------------------------------------------------------------- DailyDeal

def dailydeal(days=75):
    """WordPress 'product' posts (shown under /deal/) titled '... gratis testen'.
    Campaign dates exist only as prose, so the latest date named in the post is
    taken as its end."""
    after = (TODAY - dt.timedelta(days=days)).isoformat() + "T00:00:00"
    posts, pg = [], 1
    while pg <= 5:
        api = ("https://www.dailydeal.de/wp-json/wp/v2/product?search=gratis%20testen"
               f"&per_page=100&page={pg}&after={after}&_fields=id,date,link,title")
        try:
            _, body = get(api)
            batch = json.loads(body)
        except Exception:
            break
        if not isinstance(batch, list) or not batch:
            break
        posts += batch
        if len(batch) < 100:
            break
        pg += 1
    out = []
    for p in posts:
        title = clean(p["title"]["rendered"])
        if not re.search(r"gratis|kostenlos|geld zur", title, re.I):
            continue
        try:
            _, page = get(p["link"], tries=2)
        except Exception:
            continue
        time.sleep(0.3)
        soup = BeautifulSoup(page, "html.parser")
        btn = next((a for a in soup.find_all("a")
                    if "Zum Deal" in a.get_text() and "btn-warning" in (a.get("class") or [])), None)
        box = btn
        for _ in range(4):
            box = box.parent if box is not None else None
        body = box.get_text(" ", strip=True) if box is not None else ""
        body = re.sub(r"^.*?Zum Deal\s*\d{2}\.\d{2}\.\d{4}\s*-\s*[\d:]+\s*", "", body)
        posted = dt.date.fromisoformat(p["date"][:10])
        dates = [d for d in all_dates(body, posted.year) if d >= posted - dt.timedelta(days=60)]
        until = max(dates) if dates else None
        out.append(offer(
            "dailydeal", re.sub(r"\s*gratis testen\.?$", "", title, flags=re.I) + " gratis testen",
            url=strip_tracking(btn["href"]) if btn else None, source_url=p["link"],
            image=og_image(page), until=iso(until), text=body[:700] or None,
            added=iso(posted),
        ))
    return out


# ---------------------------------------------------------- Geldschnurrbart

def geldschnurrbart():
    """A hand-checked table of ~15 running campaigns. No links or images; it
    mainly confirms what the other sources list."""
    _, page = get(SOURCES["geldschnurrbart"]["url"])
    soup = BeautifulSoup(page, "html.parser")
    out = []
    for table in soup.find_all("table"):
        head = [th.get_text(" ", strip=True) for th in table.find_all("th")]
        if not any("Aktion" in h for h in head):
            continue
        for tr in table.find_all("tr"):
            tds = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
            if len(tds) < 3:
                continue
            gets = tds[1]
            kind = "gratis" if re.search(r"100\s*%|Kaufpreis|bis\s+[\d,]+\s*€", gets) else "teil"
            out.append(offer(
                "geldschnurrbart", tds[0], source_url=SOURCES["geldschnurrbart"]["url"],
                until=iso(parse_date(tds[2])), kind=kind,
                text=(f"Du bekommst: {gets}. " + (tds[3] if len(tds) > 3 else "")).strip(),
            ))
    return out


# -------------------------------------------------------- Google-Sheet list

SHEET_ID = "1wcqckNai9SyRbQLt-pj6FHzGM7sypoET9glyAE05u2E"
SHEET_TABS = {"100% Cashback": "gratis", "Anteilige Cashbacks": "teil"}
# The third tab, "Gebrauchsgegenstände", lists TV/camera cashbacks of 30–2000 €
# -- rebates on big purchases, not something to try for free.


def sheet():
    """The community list kept by mydealz users (linked from Geldschnurrbart).
    Richest source: quota, start time, receipt type, both deadlines."""
    _, view = get(SOURCES["sheet"]["url"])
    tabs = dict((n, g) for n, g in re.findall(r'\{name: "([^"]+)", pageUrl: "[^"]*", gid: "(\d+)"', view))
    out = []
    for tab, kind in SHEET_TABS.items():
        gid = tabs.get(tab)
        if not gid:
            continue
        _, body = get(f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&gid={gid}")
        rows = list(csv.reader(io.StringIO(body)))
        if not rows:
            continue
        hdr = [re.sub(r"\s+", " ", h) for h in rows[0]]

        def col(row, pat):
            for i, h in enumerate(hdr):
                if re.search(pat, h) and i < len(row):
                    return row[i].strip()
            return ""
        for r in rows[1:]:
            name = col(r, r"Aktionsbeschreibung")
            ende = col(r, r"Aktions- ende|Aktionsende")
            page = col(r, r"Aktionsseite")
            if not name or not (ende or page) or name.startswith(("►", "Alle Angaben", "Fehler")):
                continue
            lines = [l.strip() for l in name.splitlines() if l.strip()]
            title = lines[0]
            m = re.search(r"\bab\s+(\d{1,2}\.\d{1,2}\.(?:\d{4})?)", title)
            until = parse_date(ende)
            start = parse_date(m[1], until.year if until else None) if m else None
            if m:
                title = clean(title[:m.start()])
            sms = col(r, r"SMS")
            out.append(offer(
                "sheet", title, kind=kind,
                url=strip_tracking(page) if page.startswith("http") else None,
                source_url=col(r, r"mydealz") or SOURCES["sheet"]["url"],
                until=iso(until), start=iso(start),
                text=" ".join(lines[1:]) or None,
                quota=clean(col(r, r"^Kontingent|Kontingent$")) or None,
                start_time=clean(col(r, r"Zeitpunkt")) if col(r, r"Zeitpunkt") not in ("-", ".") else None,
                receipt=col(r, r"Kaufbeleg") or None,
                where=("SMS-Bestätigung nötig" if sms.lower().startswith("ja") else None),
                added=iso(parse_date(col(r, r"Hinzu"))),
            ))
    return out


READERS = {"sparwelt": sparwelt, "dealdoktor": dealdoktor, "dailydeal": dailydeal,
           "geldschnurrbart": geldschnurrbart, "sheet": sheet}
