"""Generate the dark theme (frontend/public/styles/dark/*.css) from the portal's light stylesheets.

The stylesheets hard-code most colours, so dark mode is derived rule by rule: every declaration that sets a colour is
repeated under :where(html[data-theme="dark"]) with the colour re-mapped. Light surfaces become dark surfaces, dark text
becomes light text, and saturated brand and status colours (the ShimentoX yellow, green, red) keep their hue.

The cascade is kept exactly: :where() adds no specificity, and index.html loads each dark file straight after the light
file it comes from, so whichever rule wins in the light theme also wins in the dark theme.

Run `npm run theme:dark` after changing a stylesheet. The files in styles/dark/ are generated; do not edit them.
"""
import colorsys
import re
from pathlib import Path

STYLES = Path(__file__).resolve().parents[1] / 'public/styles'
INDEX = STYLES.parent / 'index.html'
OUTPUT = STYLES / 'dark'
ROOT = 'html[data-theme="dark"]'
DARK = f':where({ROOT})'

NAMED = {'white': (255, 255, 255), 'black': (0, 0, 0)}
COLOR = re.compile(r'#[0-9a-fA-F]{8}\b|#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3,4}\b|rgba?\([^)]*\)|\b(?:white|black)\b')
TEXT_PROPS = ('color', 'fill', 'stroke', 'caret-color', 'text-decoration-color', '-webkit-text-fill-color', 'accent-color')
BORDER_PROPS = ('border', 'outline', 'column-rule')
BG_PROPS = ('background', 'scrollbar-color')

# Browser defaults the light theme relies on (form fields, native controls), with no specificity so any rule wins.
BASE = f'''{ROOT}{{color-scheme:dark}}
{DARK} body{{background:#121619;color:#dfe5e8}}
{DARK} input,{DARK} select,{DARK} textarea,{DARK} button{{color:#e3e8eb}}
{DARK} input,{DARK} select,{DARK} textarea{{background-color:#1a2024;border-color:#3a454b}}
{DARK} input::placeholder,{DARK} textarea::placeholder{{color:#8a979d}}
{DARK} option{{background:#1a2024;color:#e3e8eb}}
{DARK} hr{{border-color:#2f383d}}'''


def parse(token):
    if token in NAMED:
        return (*NAMED[token], None)
    if token.startswith('#'):
        h = token[1:]
        if len(h) in (3, 4):
            h = ''.join(c * 2 for c in h)
        alpha = int(h[6:8], 16) / 255 if len(h) == 8 else None
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha
    parts = [p for p in re.split(r'[,\s/]+', token[token.index('(') + 1:-1]) if p]
    try:
        rgb = [float(p.rstrip('%')) * (2.55 if p.endswith('%') else 1) for p in parts[:3]]
        alpha = float(parts[3].rstrip('%')) / (100 if parts[3].endswith('%') else 1) if len(parts) > 3 else None
    except (ValueError, IndexError):
        return None
    return (*rgb, alpha)


def emit(r, g, b, alpha):
    r, g, b = (max(0, min(255, round(v))) for v in (r, g, b))
    if alpha is None or alpha >= 1:
        return f'#{r:02x}{g:02x}{b:02x}'
    return f'rgba({r},{g},{b},{round(alpha, 3)})'


def remap(color, kind):
    """kind: 'bg' (surfaces and tints), 'border', 'text' or 'shadow'."""
    r, g, b, alpha = color
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    if kind == 'shadow':
        a = alpha if alpha is not None else 1
        if l >= 0.85:                # White highlights (inset sheen) fade to a faint edge.
            return emit(255, 255, 255, round(a * 0.25, 3))
        if s >= 0.5 and l >= 0.4:    # Coloured glows (the yellow button glow, focus rings) are kept.
            return emit(r, g, b, alpha)
        return emit(0, 0, 0, min(0.6, a * 2.2))  # Shadows stay shadows, a little stronger on a dark page.
    if kind == 'bg':
        if l >= 0.78:                # White and pale tints become dark surfaces, keeping a hint of their tint.
            l, s = 0.115 + (1 - l) * 0.55, s * 0.45
        elif l <= 0.28:              # Already-dark panels (sidebar, code blocks) stay dark.
            l = max(0.07, l * 0.75)
        elif s < 0.25:               # Mid-grey fills become a lighter dark grey.
            l = 0.30 + (l - 0.28) * 0.35
        # Saturated mid colours (brand yellow, status green and red) are kept.
    elif kind == 'border':
        if l >= 0.70:
            l, s = 0.25 + (1 - l) * 0.45, s * 0.5
        elif l <= 0.30 and s < 0.3:
            l = 0.42
    else:
        if l <= 0.55:                # Dark text becomes light text of the same hue: ink to near-white, gold stays gold.
            l = 0.93 - l * 0.55
            if s > 0.35:
                l = max(l, 0.70)
        elif l < 0.75 and s < 0.3:   # Grey secondary text gets a little lighter for contrast.
            l += 0.08
    r, g, b = colorsys.hls_to_rgb(h, max(0, min(1, l)), max(0, min(1, s)))
    return emit(r * 255, g * 255, b * 255, alpha)


def kind_of(prop):
    prop = prop.strip().lower()
    if prop.startswith('--'):
        if re.search(r'line|border|rule', prop):
            return 'border'
        if re.search(r'primary|secondary|accent|brand|strong|thumb', prop):
            return None              # Brand and emphasis colours are kept.
        if re.search(r'ink|muted|text|teal|fg|color', prop):
            return 'text'
        return 'bg'
    if prop in ('box-shadow', 'text-shadow'):
        return 'shadow'
    if prop in TEXT_PROPS:
        return 'text'
    if prop.startswith(BORDER_PROPS):
        return 'border'
    if prop.startswith(BG_PROPS):
        return 'bg'
    return None


def convert_value(prop, value):
    kind = kind_of(prop)
    if kind is None or 'url(' in value:
        return None
    changed = False

    def swap(match):
        nonlocal changed
        parsed = parse(match.group(0))
        if parsed is None:
            return match.group(0)
        out = remap(parsed, kind)
        changed = changed or out != emit(*parsed)
        return out
    result = COLOR.sub(swap, value)
    return result if changed else None


ON_BRIGHT = '#1b2226'  # Text on the ShimentoX yellow (buttons, active navigation) stays dark in both themes.
BRAND_VARS = re.compile(r'var\(--(primary|secondary|accent)\b')


def bright_background(value):
    """A brand-yellow or similar bright, saturated fill that is kept in dark mode."""
    if BRAND_VARS.search(value):
        return True
    for match in COLOR.finditer(value):
        parsed = parse(match.group(0))
        if parsed and (parsed[3] is None or parsed[3] > 0.8):
            _, l, s = colorsys.rgb_to_hls(parsed[0] / 255, parsed[1] / 255, parsed[2] / 255)
            if 0.45 <= l < 0.78 and s >= 0.6:
                return True
    return False


def dark_text(value):
    if re.search(r'var\(--(ink|brand-charcoal|teal|muted)\b', value):
        return True
    parsed = next((parse(m.group(0)) for m in COLOR.finditer(value)), None)
    return bool(parsed) and colorsys.rgb_to_hls(parsed[0] / 255, parsed[1] / 255, parsed[2] / 255)[1] <= 0.55


def blocks(css):
    """(prelude, body) for each top-level block, with nested braces matched."""
    i, n = 0, len(css)
    while i < n:
        start = css.find('{', i)
        if start == -1:
            return
        depth, j = 1, start + 1
        while j < n and depth:
            depth += {'{': 1, '}': -1}.get(css[j], 0)
            j += 1
        yield css[i:start].strip(), css[start + 1:j - 1]
        i = j


def declarations(body):
    out, current, depth = [], '', 0
    for char in body:
        depth += {'(': 1, ')': -1}.get(char, 0)
        if char == ';' and depth == 0:
            out.append(current)
            current = ''
        else:
            current += char
    out.append(current)
    return [d for d in (x.strip() for x in out) if ':' in d]


def scope(selector):
    selector = selector.strip()
    for root in (':root', 'html'):
        if selector.startswith(root):
            return ROOT + selector[len(root):]  # The same element: variables are redefined in place.
    return f'{DARK} {selector}'


def convert(css):
    out = []
    for prelude, body in blocks(css):
        if prelude.startswith(('@keyframes', '@-webkit-keyframes', '@font-face', '@import', '@media print')):
            continue
        if prelude.startswith('@'):
            inner = convert(body)
            if inner:
                out.append(f'{prelude}{{{inner}}}')
            continue
        rules, items = [], [d.split(':', 1) for d in declarations(body)]
        bright = any(p.strip().lower() in ('background', 'background-color') and bright_background(v) for p, v in items)
        colors = [v for p, v in items if p.strip().lower() == 'color']
        for prop, value in items:
            important = '!important' in value
            if bright and prop.strip().lower() == 'color':
                continue  # Handled below: text on a bright brand colour stays dark.
            new = convert_value(prop, value.replace('!important', '').strip())
            if new is not None:
                rules.append(f'{prop.strip()}:{new}{"!important" if important else ""}')
        if bright and (not colors or any(dark_text(v) for v in colors)):
            important = any('!important' in v for v in colors)
            rules.append(f'color:{ON_BRIGHT}{"!important" if important else ""}')
        if rules:
            out.append(','.join(scope(s) for s in re.split(r',(?![^(]*\))', prelude)) + '{' + ';'.join(rules) + '}')
    return '\n'.join(out)


def sources():
    """Light stylesheets in the order index.html loads them (dark files are skipped)."""
    return re.findall(r'href="styles/([a-z0-9-]+\.css)"', INDEX.read_text(encoding='utf-8'))


def main():
    OUTPUT.mkdir(exist_ok=True)
    header = '/* Generated by frontend/tools/build_dark_theme.py from {}. Do not edit; run npm run theme:dark. */\n'
    (OUTPUT / 'base.css').write_text(header.format('browser defaults') + BASE + '\n', encoding='utf-8')
    for name in sources():
        css = re.sub(r'/\*.*?\*/', '', (STYLES / name).read_text(encoding='utf-8'), flags=re.S)
        converted = convert(css)
        (OUTPUT / name).write_text(header.format('styles/' + name) + converted + '\n', encoding='utf-8')
        print(f'styles/dark/{name}: {len(converted.splitlines())} rules')


if __name__ == '__main__':
    main()
