"""HTML for the browser/LAN front end — rendered as plain strings, standard
library only (``html.escape``). No template engine, no pip.

The look echoes the desktop HCW kit: one Radiant-Orange accent for the primary
action, quiet slate surfaces, and a left rail + work stage. It is theme-aware
(follows the browser's light/dark preference) and responsive, so a site engineer
on a phone gets the same data as the office desktop. Everything is inlined —
one self-contained document per response — so there are no extra asset requests
to serve or cache.
"""

import html

BRAND = 'Construction OS'
ACCENT = '#FF4F18'


def esc(value):
    return html.escape('' if value is None else str(value), quote=True)


def money(value):
    try:
        return '₹ {:,.0f}'.format(round(float(value or 0)))
    except (TypeError, ValueError):
        return esc(value)


_CSS = """
:root{
  --accent:#FF4F18; --bg:#F4F5F7; --surface:#FFFFFF; --ink:#1B1E23;
  --muted:#5B616B; --line:#E3E6EA; --rail:#20242B; --rail-ink:#E7EAF0;
  --good:#1B7F5A; --warn:#B26A00; --bad:#C8442E;
}
@media (prefers-color-scheme:dark){
  :root{ --bg:#12151A; --surface:#191C21; --ink:#E7EAF0; --muted:#9AA2AE;
    --line:#2A2F37; --rail:#0F1216; --rail-ink:#E7EAF0;
    --good:#4CC29A; --warn:#FFB25C; --bad:#F07862; }
}
*{box-sizing:border-box}
body{margin:0;font:15px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
  background:var(--bg);color:var(--ink)}
a{color:inherit;text-decoration:none}
.layout{display:flex;min-height:100vh}
.rail{width:230px;flex:0 0 230px;background:var(--rail);color:var(--rail-ink);
  padding:18px 0;position:sticky;top:0;height:100vh;overflow:auto}
.brand{font-weight:700;font-size:18px;padding:0 20px 14px;display:flex;
  align-items:center;gap:9px}
.brand .dot{width:11px;height:11px;border-radius:3px;background:var(--accent);
  display:inline-block}
.navgroup{padding:12px 20px 4px;font-size:11px;letter-spacing:.08em;
  text-transform:uppercase;color:#8B93A1}
.rail a{display:block;padding:7px 20px;color:var(--rail-ink);opacity:.82;
  font-size:14px;border-left:3px solid transparent}
.rail a:hover{opacity:1;background:rgba(255,255,255,.05)}
.rail a.on{opacity:1;border-left-color:var(--accent);background:rgba(255,79,24,.12)}
.main{flex:1;min-width:0;display:flex;flex-direction:column}
.topbar{display:flex;align-items:center;justify-content:space-between;
  padding:12px 22px;border-bottom:1px solid var(--line);background:var(--surface)}
.topbar .who{color:var(--muted);font-size:13px}
.content{padding:22px;max-width:1200px;width:100%}
h1{font-size:22px;margin:0 0 4px}
h2{font-size:15px;margin:22px 0 10px;color:var(--muted);font-weight:600;
  text-transform:uppercase;letter-spacing:.05em}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:12px;
  padding:14px 16px}
.card .k{color:var(--muted);font-size:12px;text-transform:uppercase;
  letter-spacing:.04em}
.card .v{font-size:22px;font-weight:700;margin-top:4px}
.adv{background:var(--surface);border:1px solid var(--line);border-left-width:4px;
  border-radius:10px;padding:12px 14px;margin-bottom:10px}
.adv.act{border-left-color:var(--bad)} .adv.watch{border-left-color:var(--warn)}
.adv.good{border-left-color:var(--good)} .adv.info{border-left-color:var(--muted)}
.adv .t{font-weight:600}
.adv .m{color:var(--muted);font-size:13px;margin-top:3px}
.pill{display:inline-block;font-size:11px;padding:1px 8px;border-radius:20px;
  border:1px solid var(--line);color:var(--muted);margin-left:6px}
table{width:100%;border-collapse:collapse;background:var(--surface);
  border:1px solid var(--line);border-radius:10px;overflow:hidden}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--line);
  font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  max-width:320px}
th{background:var(--bg);color:var(--muted);font-weight:600;font-size:12px;
  text-transform:uppercase;letter-spacing:.03em}
tr:last-child td{border-bottom:none}
tr:hover td{background:rgba(127,127,127,.05)}
.tablewrap{overflow-x:auto}
.btn{display:inline-block;background:var(--accent);color:#fff;border:none;
  border-radius:9px;padding:9px 16px;font-size:14px;font-weight:600;cursor:pointer}
.btn.ghost{background:transparent;color:var(--muted);border:1px solid var(--line)}
input[type=text],input[type=password],input[type=search]{
  width:100%;padding:9px 11px;border:1px solid var(--line);border-radius:9px;
  background:var(--surface);color:var(--ink);font-size:14px}
.toolbar{display:flex;gap:10px;align-items:center;margin-bottom:14px;flex-wrap:wrap}
.toolbar form{display:flex;gap:8px;flex:1;min-width:220px}
.banner{background:#FFF3E0;border:1px solid #FFCC80;color:#8A4B00;padding:9px 14px;
  border-radius:9px;margin-bottom:16px;font-size:13px}
@media (prefers-color-scheme:dark){.banner{background:#2A1E10;border-color:#5A3B14;color:#FFC98A}}
.muted{color:var(--muted)} .right{text-align:right}
.pager{display:flex;gap:8px;align-items:center;margin-top:14px;color:var(--muted);
  font-size:13px}
.pager a{border:1px solid var(--line);border-radius:8px;padding:5px 11px}
.dl{display:grid;grid-template-columns:190px 1fr;gap:2px 16px;background:var(--surface);
  border:1px solid var(--line);border-radius:10px;padding:16px}
.dl dt{color:var(--muted);font-size:13px;padding:6px 0;border-bottom:1px solid var(--line)}
.dl dd{margin:0;padding:6px 0;border-bottom:1px solid var(--line);
  word-break:break-word}
/* Login */
.login{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
.loginbox{background:var(--surface);border:1px solid var(--line);border-radius:16px;
  padding:30px;width:100%;max-width:380px}
.loginbox h1{font-size:20px;margin-bottom:4px}
.loginbox .field{margin:14px 0}
.loginbox label{display:block;font-size:13px;color:var(--muted);margin-bottom:5px}
.err{color:var(--bad);font-size:13px;margin-top:10px}
@media (max-width:720px){
  .layout{flex-direction:column}
  .rail{width:auto;flex:none;height:auto;position:static;display:flex;
    flex-wrap:wrap;gap:2px;padding:10px}
  .rail .brand{width:100%;padding:6px 10px}
  .navgroup{display:none}
  .rail a{border-left:none;border-radius:8px;padding:6px 10px}
  .rail a.on{background:rgba(255,79,24,.18)}
}
"""


def _doc(title, body):
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>{} — {}</title><style>{}</style></head>'
            '<body>{}</body></html>').format(esc(title), esc(BRAND), _CSS, body)


def _rail(nav, active):
    """nav = ordered list of (group, [(href, label, key), ...])."""
    out = ['<nav class="rail"><div class="brand"><span class="dot"></span>{}'
           '</div>'.format(esc(BRAND))]
    for group, items in nav:
        if group:
            out.append('<div class="navgroup">{}</div>'.format(esc(group)))
        for href, label, key in items:
            on = ' on' if key == active else ''
            out.append('<a class="{}" href="{}">{}</a>'.format(
                on.strip(), esc(href), esc(label)))
    out.append('</nav>')
    return ''.join(out)


def page(title, body, *, user='', nav=None, active='', warning=''):
    who = ('<span class="who">{} &middot; <a href="/logout">Sign out</a></span>'
           .format(esc(user)) if user else '')
    banner = ('<div class="banner">{}</div>'.format(esc(warning))
              if warning else '')
    inner = (
        '<div class="layout">{rail}<div class="main">'
        '<div class="topbar"><strong>{title}</strong>{who}</div>'
        '<div class="content">{banner}{body}</div></div></div>'
    ).format(rail=_rail(nav or [], active), title=esc(title), who=who,
             banner=banner, body=body)
    return _doc(title, inner)


def table(columns, rows, *, link=None):
    """columns = list of header strings. rows = list of lists of cell values.
    link (optional) = function(row_index) -> href to make each row clickable."""
    head = ''.join('<th>{}</th>'.format(esc(c)) for c in columns)
    body = []
    for i, row in enumerate(rows):
        href = link(i) if link else None
        cells = ''.join('<td>{}</td>'.format(esc(_trim(c))) for c in row)
        if href:
            body.append('<tr onclick="location=\'{}\'" style="cursor:pointer">{}'
                        '</tr>'.format(esc(href), cells))
        else:
            body.append('<tr>{}</tr>'.format(cells))
    return ('<div class="tablewrap"><table><thead><tr>{}</tr></thead>'
            '<tbody>{}</tbody></table></div>').format(head, ''.join(body))


def _trim(value, limit=120):
    s = '' if value is None else str(value)
    return s if len(s) <= limit else s[:limit - 1] + '…'


def login_page(*, error='', first_run=False, csrf='', host_note=''):
    title = 'Create the first admin' if first_run else 'Sign in'
    intro = ('No accounts yet — create the administrator to secure LAN access.'
             if first_run else 'Sign in to {}.'.format(BRAND))
    err = '<div class="err">{}</div>'.format(esc(error)) if error else ''
    note = ('<p class="muted" style="font-size:12px;margin-top:16px">{}</p>'
            .format(esc(host_note)) if host_note else '')
    body = (
        '<div class="login"><form class="loginbox" method="post" action="/login">'
        '<div class="brand" style="padding:0 0 6px"><span class="dot"></span>{brand}</div>'
        '<h1>{title}</h1><p class="muted">{intro}</p>'
        '<input type="hidden" name="csrf" value="{csrf}">'
        '<div class="field"><label>Username</label>'
        '<input type="text" name="username" autofocus autocomplete="username"></div>'
        '<div class="field"><label>Password</label>'
        '<input type="password" name="password" autocomplete="current-password"></div>'
        '{err}'
        '<div class="field"><button class="btn" type="submit" style="width:100%">'
        '{cta}</button></div>{note}</form></div>'
    ).format(brand=esc(BRAND), title=esc(title), intro=esc(intro), csrf=esc(csrf),
             err=err, cta='Create admin' if first_run else 'Sign in', note=note)
    return _doc(title, body)
