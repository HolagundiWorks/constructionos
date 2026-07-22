"""HTML for the browser/LAN front end — rendered as plain strings, standard
library only (``html.escape``). No template engine, no pip.

The look is the **HCW-UI design language**, driven from the *same* ``tokens``
module as the desktop theme (a strict project rule: one design system, two
skins). That means the exact kit values — Fog-Gray canvas, Pure-White cards,
Coal-Black ink, the single **Radiant-Orange** accent for actions only — and the
kit's shape law: **square surfaces (0 radius)**, buttons 4px, dialogs 8px, an
instrument **rail** (a white panel, not a dark sidebar) whose active row wears a
3px accent inset rule. It is theme-aware (follows the browser's light/dark) and
responsive. Everything is inlined so there are no extra asset requests.
"""

import html

import tokens

BRAND = 'Construction OS'
ACCENT = tokens.LIGHT['accent']


def esc(value):
    return html.escape('' if value is None else str(value), quote=True)


def money(value):
    try:
        return '₹ {:,.0f}'.format(round(float(value or 0)))
    except (TypeError, ValueError):
        return esc(value)


# ── CSS variables generated from the shared design tokens ─────────────────────
# (css-var-name, token-key). A test asserts the emitted CSS carries the token
# values, so the web skin can't drift from the desktop / the kit.
_VARMAP = [
    ('bg', 'canvas'), ('surface', 'surface'), ('surface2', 'surface2'),
    ('rail', 'rail'), ('ink', 'ink'), ('muted', 'muted'), ('helper', 'helper'),
    ('line', 'hairline'), ('accent', 'accent'), ('accent-soft', 'accent_soft'),
    ('accent-dark', 'accent_dark'), ('on-accent', 'on_accent'),
    ('hover', 'hover'), ('good', 'success'), ('warn', 'warning'),
    ('bad', 'error'), ('info', 'info'),
]


def _vars(scheme):
    return ''.join('--{}:{};'.format(css, scheme[key]) for css, key in _VARMAP)


_SHAPE = ('--r-btn:{}px;--r-dialog:{}px;--rail-w:{}px;--content-max:{}px;'.format(
    tokens.BUTTON_RADIUS, tokens.DIALOG_RADIUS,
    tokens.LAYOUT['rail_width'], tokens.LAYOUT['content_max_width']))

# Static rules reference the vars above. Square by default (radius 0); only
# buttons (--r-btn) and dialog cards (--r-dialog) round.
_STATIC = """
*{box-sizing:border-box}
body{margin:0;font:14px/1.55 __FONTSTACK__;background:var(--bg);color:var(--ink)}
a{color:inherit;text-decoration:none}
.layout{display:flex;min-height:100vh}
.rail{width:var(--rail-w);flex:0 0 var(--rail-w);background:var(--rail);
  color:var(--ink);padding:16px 0;position:sticky;top:0;height:100vh;
  overflow:auto;border-right:1px solid var(--line)}
.brand{font-weight:650;font-size:16px;padding:0 20px 14px;display:flex;
  align-items:center;gap:9px;color:var(--ink)}
.brand .dot{width:11px;height:11px;background:var(--accent);display:inline-block}
.navgroup{padding:14px 20px 4px;font-size:11px;letter-spacing:.06em;
  text-transform:uppercase;color:var(--helper);font-weight:600}
.rail a{display:block;padding:7px 20px;color:var(--muted);font-size:13px;
  border-left:3px solid transparent}
.rail a:hover{color:var(--ink);background:var(--hover)}
.rail a.on{color:var(--ink);font-weight:600;border-left-color:var(--accent);
  background:var(--surface2)}
.main{flex:1;min-width:0;display:flex;flex-direction:column}
.topbar{display:flex;align-items:center;justify-content:space-between;
  padding:12px 24px;border-bottom:1px solid var(--line);background:var(--surface)}
.topbar .who{color:var(--muted);font-size:13px}
.topbar a{color:var(--info)}
.content{padding:24px;max-width:var(--content-max);width:100%}
h1{font-size:20px;line-height:1.3;margin:0 0 4px;font-weight:650;
  letter-spacing:-.005em}
h2{font-size:11px;margin:24px 0 10px;color:var(--helper);font-weight:600;
  text-transform:uppercase;letter-spacing:.06em}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px}
.card{background:var(--surface);border:1px solid var(--line);padding:16px}
.card .k{color:var(--helper);font-size:11px;text-transform:uppercase;
  letter-spacing:.06em;font-weight:600}
.card .v{font-size:24px;font-weight:650;margin-top:6px;letter-spacing:-.01em}
.adv{background:var(--surface);border:1px solid var(--line);border-left-width:3px;
  padding:12px 16px;margin-bottom:8px}
.adv.act{border-left-color:var(--bad)} .adv.watch{border-left-color:var(--warn)}
.adv.good{border-left-color:var(--good)} .adv.info{border-left-color:var(--muted)}
.adv .t{font-weight:600}
.adv .m{color:var(--muted);font-size:13px;margin-top:3px}
.pill{display:inline-block;font-size:11px;padding:1px 8px;border-radius:var(--r-btn);
  border:1px solid var(--line);color:var(--muted);margin-left:8px}
table{width:100%;border-collapse:collapse;background:var(--surface);
  border:1px solid var(--line)}
th,td{text-align:left;padding:10px 14px;border-bottom:1px solid var(--line);
  font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  max-width:320px}
th{background:var(--surface2);color:var(--helper);font-weight:600;font-size:11px;
  text-transform:uppercase;letter-spacing:.04em}
tr:last-child td{border-bottom:none}
tr:hover td{background:var(--hover)}
.tablewrap{overflow-x:auto}
.btn{display:inline-block;background:var(--accent);color:var(--on-accent);
  border:1px solid var(--accent);border-radius:var(--r-btn);padding:9px 16px;
  font-size:13px;font-weight:600;cursor:pointer}
.btn:hover{background:var(--accent-dark);border-color:var(--accent-dark)}
.btn.ghost{background:transparent;color:var(--muted);border:1px solid var(--line)}
.btn.ghost:hover{background:var(--hover);color:var(--ink)}
input[type=text],input[type=password],input[type=search],select,textarea{
  width:100%;padding:9px 11px;border:1px solid var(--line);background:var(--surface);
  color:var(--ink);font-size:14px;font-family:inherit;border-radius:0}
input:focus,select:focus,textarea:focus{outline:none;border-color:var(--accent)}
textarea{resize:vertical}
.toolbar{display:flex;gap:10px;align-items:center;margin-bottom:16px;flex-wrap:wrap}
.toolbar form{display:flex;gap:8px;flex:1;min-width:220px}
.banner{background:var(--surface);border:1px solid var(--warn);border-left:3px solid var(--warn);
  color:var(--ink);padding:10px 14px;border-radius:var(--r-dialog);margin-bottom:16px;
  font-size:13px}
.muted{color:var(--muted)} .right{text-align:right}
.pager{display:flex;gap:8px;align-items:center;margin-top:16px;color:var(--muted);
  font-size:13px}
.pager a{border:1px solid var(--line);border-radius:var(--r-btn);padding:5px 11px}
.dl{display:grid;grid-template-columns:190px 1fr;gap:0 16px;background:var(--surface);
  border:1px solid var(--line);padding:16px}
.dl dt{color:var(--helper);font-size:12px;padding:7px 0;border-bottom:1px solid var(--line)}
.dl dd{margin:0;padding:7px 0;border-bottom:1px solid var(--line);word-break:break-word}
/* Forms */
.frow{margin:14px 0;max-width:540px}
.frow label{display:block;font-size:13px;color:var(--muted);margin-bottom:5px;font-weight:500}
.formbtns{display:flex;gap:10px;margin-top:22px;max-width:540px}
.err-list{background:var(--surface);border:1px solid var(--bad);border-left:3px solid var(--bad);
  color:var(--ink);border-radius:var(--r-dialog);padding:10px 14px;margin-bottom:16px;font-size:13px}
.rowbtns{display:flex;gap:10px;margin:14px 0}
form.inline{display:inline}
/* Login (a dialog card — the one rounded surface) */
.login{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
.loginbox{background:var(--surface);border:1px solid var(--line);
  border-radius:var(--r-dialog);padding:32px;width:100%;max-width:380px}
.loginbox h1{font-size:20px;margin-bottom:4px}
.loginbox .field{margin:16px 0}
.loginbox label{display:block;font-size:13px;color:var(--muted);margin-bottom:6px;font-weight:500}
.err{color:var(--bad);font-size:13px;margin-top:10px}
@media (max-width:720px){
  .layout{flex-direction:column}
  .rail{width:auto;flex:none;height:auto;position:static;display:flex;
    flex-wrap:wrap;gap:2px;padding:10px;border-right:none;
    border-bottom:1px solid var(--line)}
  .rail .brand{width:100%;padding:6px 10px}
  .navgroup{display:none}
  .rail a{border-left:none;padding:6px 10px}
  .rail a.on{background:var(--surface2)}
}
""".replace('__FONTSTACK__', tokens.FONT_STACK)

_CSS = (':root{' + _vars(tokens.LIGHT) + _SHAPE + '}'
        '@media (prefers-color-scheme:dark){:root{' + _vars(tokens.DARK) + '}}'
        + _STATIC)


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


# ------------------------------------------------------------------- forms
def control(kind, name, value, options=None):
    """One form input for a field ``kind``. ``options`` = [(value, label), ...]
    for combo/fk."""
    v = esc('' if value is None else value)
    n = esc(name)
    if kind == 'number':
        return ('<input type="text" inputmode="decimal" name="{}" value="{}">'
                .format(n, v))
    if kind == 'textarea':
        return '<textarea name="{}" rows="3">{}</textarea>'.format(n, v)
    if kind in ('combo', 'fk'):
        cur = '' if value is None else str(value)
        opts = ['<option value="">—</option>'] if kind == 'fk' else []
        for val, label in (options or []):
            sel = ' selected' if str(val) == cur else ''
            opts.append('<option value="{}"{}>{}</option>'.format(
                esc(val), sel, esc(label)))
        return '<select name="{}">{}</select>'.format(n, ''.join(opts))
    return '<input type="text" name="{}" value="{}">'.format(n, v)


def field_row(label_text, control_html):
    return '<div class="frow"><label>{}</label>{}</div>'.format(
        esc(label_text), control_html)


def errors(messages):
    if not messages:
        return ''
    items = ''.join('<li>{}</li>'.format(esc(m)) for m in messages)
    return '<div class="err-list"><ul style="margin:0;padding-left:18px">{}' \
           '</ul></div>'.format(items)


def form(action, rows_html, csrf, *, submit='Save', cancel_href=''):
    cancel = ('<a class="btn ghost" href="{}">Cancel</a>'.format(esc(cancel_href))
              if cancel_href else '')
    return (
        '<form method="post" action="{action}">'
        '<input type="hidden" name="csrf" value="{csrf}">{rows}'
        '<div class="formbtns"><button class="btn" type="submit">{submit}</button>'
        '{cancel}</div></form>'
    ).format(action=esc(action), csrf=esc(csrf), rows=rows_html,
             submit=esc(submit), cancel=cancel)


def post_button(action, csrf, label, *, confirm='', ghost=True):
    """A one-button POST form (for delete) — POST, not a link, so it can't be
    triggered by a bare GET."""
    onsubmit = (' onsubmit="return confirm(\'{}\')"'.format(esc(confirm))
                if confirm else '')
    cls = 'btn ghost' if ghost else 'btn'
    return (
        '<form method="post" action="{action}" class="inline"{onsubmit}>'
        '<input type="hidden" name="csrf" value="{csrf}">'
        '<button class="{cls}" type="submit">{label}</button></form>'
    ).format(action=esc(action), onsubmit=onsubmit, csrf=esc(csrf), cls=cls,
             label=esc(label))


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
