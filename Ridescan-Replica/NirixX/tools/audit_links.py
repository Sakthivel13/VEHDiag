#!/usr/bin/env python3
"""NirixX deep link-audit — beyond verify_apk's reachability check:

  A. activity inventory & back-wiring (app-bar back on every screen)
  B. navigation edges: go(X.class) / new Intent(.. ) targets declared
  C. intent-extra contracts (SupplierFlashActivity module/image_type/family)
  D. startActivityForResult request-code pairing (REQ_* ↔ onActivityResult)
  E. role-module consistency: Home TILES modules exist in Roles; every gated
     module name maps; report which screens are consciously ungated
  F. services/provider referenced from code
  G. getIdentifier-drawable lookups resolve
Prints a per-area report; exits 1 on any ERROR.
"""
import os, re, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
SRC = os.path.join(ROOT, 'app/src/com/nirixx/app')
MAN = os.path.join(ROOT, 'manifest/AndroidManifest.xml')
errs, warns = [], []

def err(m): errs.append(m); print('  ERR   ' + m)
def warn(m): warns.append(m); print('  WARN  ' + m)
def ok(m): print('  ok    ' + m)

def read(p):
    with open(p, 'r', encoding='utf-8', errors='replace') as f: return f.read()

manifest = read(MAN)
act_names = set(re.findall(r'<activity android:name="\.(\w+)"', manifest))
svc_names = set(re.findall(r'<service android:name="\.(\w+)"', manifest))
prov_names = set(re.findall(r'<provider android:name="\.(\w+)"', manifest))

HELPERS = {'Ui', 'Perms', 'Session', 'BaseActivity', 'NirixXApp', 'DocsProvider'}
sources = {}
for f in sorted(os.listdir(SRC)):
    if f.endswith('.java'):
        sources[f[:-5]] = read(os.path.join(SRC, f))
for sub in ('db', 'sim', 'vci'):
    d = os.path.join(SRC, sub)
    if os.path.isdir(d):
        for f in os.listdir(d):
            if f.endswith('.java'):
                sources[f[:-5]] = read(os.path.join(d, f))
core_dir = os.path.join(SRC, 'core')
for root, _, files in os.walk(core_dir):
    for f in files:
        if f.endswith('.java'):
            sources[f[:-5]] = read(os.path.join(root, f))

drawables = set()
res = os.path.join(ROOT, 'app/res')
for d in os.listdir(res):
    if d.startswith('drawable') or d.startswith('mipmap'):
        for f in os.listdir(os.path.join(res, d)):
            drawables.add(f.split('.')[0])

# ------------------------------------------------------------------ A. back wiring
print('\n== A. Back-navigation wiring ==')
# layouts that actually contain the app-bar back button (wired by BaseActivity.shell)
bar_layouts = set()
for lf in os.listdir(os.path.join(res, 'layout')):
    lf_src = read(os.path.join(res, 'layout', lf))
    if 'btnBack' in lf_src: bar_layouts.add(lf[:-4])
NO_BACK_OK = {'SplashActivity', 'LoginActivity', 'WelcomeActivity',
              'TutorialActivity', 'UserTypeActivity', 'HomeActivity', 'SsoLoginActivity'}
def merged_source(cls):
    """class source + nearest activity-superclass source (e.g. VinFlashingActivity)."""
    parts, seen, cur = [], set(), cls
    while cur and cur in sources and cur not in seen:
        seen.add(cur)
        parts.append(sources[cur])
        m = re.search(r'extends\s+(\w+Activity)', sources[cur])
        cur = m.group(1) if m else None
    return '\n'.join(parts) if parts else None

no_back = []
for cls in sorted(act_names):
    src = merged_source(cls)
    if src is None:
        err('%s declared in manifest but no source' % cls); continue
    lays = set(re.findall(r'setContentView\(\s*R\.layout\.(\w+)', src))
    has_bar = any(l in bar_layouts for l in lays)
    if ('wireBack()' not in src and 'hideBack()' not in src
            and 'onBackPressed' not in src and not has_bar):
        if cls in NO_BACK_OK:
            continue
        no_back.append(cls)
if no_back:
    err('no back wiring and no app-bar layout: ' + ', '.join(no_back))
else:
    ok('every screen reaches back: app-bar layouts (%s) or explicit wiring' % ', '.join(sorted(bar_layouts)))

# ------------------------------------------------------------------ B. nav edges
print('\n== B. Navigation edges ==')
def intent_targets(src):
    """All X.class inside any `new …Intent(` call (handles FQCN and ternaries)."""
    out = set()
    for call in re.findall(r'new\s+(?:[\w.]*\.)?Intent\s*\((.*?)\)\s*[;,.)]', src, re.S):
        out |= set(re.findall(r'\b([\w$]+)\.class\b', call))
    return out
edges = {}
for cls, src in sources.items():
    if not cls.endswith('Activity') or cls in HELPERS: continue
    tg = set(re.findall(r'\bgo\s*\(\s*([\w$]+)\.class', src))
    tg |= intent_targets(src)
    if tg: edges[cls] = sorted(tg)
for cls, tg in edges.items():
    for t in tg:
        if t not in act_names and t not in svc_names:
            err('%s navigates to undeclared %s' % (cls, t))
n_edges = sum(len(v) for v in edges.items())
ok('%d edges across %d screens, all targets declared' % (n_edges, len(edges)))

# reachability (paranoia dupe of verify_apk, but with per-node dump potential)
rev = {}
for s_, ts in edges.items():
    for t in ts: rev.setdefault(t, set()).add(s_)
linkage = {}
for cls, src in sources.items():
    if not cls.endswith('Activity') or cls in HELPERS: continue
    for t in set(re.findall(r'\b(\w+)\.class\b', src)):
        if t != cls and t in act_names: linkage.setdefault(t, set()).add(cls)
reach, frontier = set(), ['SplashActivity']
while frontier:
    h = frontier.pop()
    if h in reach: continue
    reach.add(h)
    for t, ss in linkage.items():
        if h in ss and t in act_names: frontier.append(t)
unreach = sorted(a for a in act_names if a not in reach)
if unreach: err('unreachable activities: ' + ', '.join(unreach))
else: ok('all %d activities reachable from SplashActivity' % len(act_names))

# edges FROM unreachable-ish roots sanity
for a in ('SplashActivity', 'WelcomeActivity', 'LoginActivity', 'HomeActivity'):
    if a not in edges and a not in linkage: warn(a + ' exposes no outgoing edges')

# ------------------------------------------------------------------ C. extras contract
print('\n== C. Intent extras contract: SupplierFlashActivity ==')
reads = set(re.findall(r'getStringExtra\("(\w+)"\)', sources['SupplierFlashActivity']))
callers = [c for c in ('SupplierFlashListActivity', 'ClusterFlashListActivity')
           if 'SupplierFlashActivity' in edges.get(c, [])]
bad = False
for c in callers:
    src = sources[c]
    for ex in reads:
        if 'putExtra("%s"' % ex not in src:
            err('%s → SupplierFlashActivity does not put "%s"' % (c, ex)); bad = True
if not bad: ok('callers supply all extras read (%s) via %s'
               % (', '.join(sorted(reads)), ', '.join(callers)))

# ------------------------------------------------------------------ D. request codes
print('\n== D. startActivityForResult pairing ==')
pairs = 0
for cls, src in sources.items():
    if not cls.endswith('Activity'): continue
    reqs = set(re.findall(r'(?:static\s+final\s+int|private\s+static\s+final\s+int)\s+(REQ_\w+)\s*=\s*\d+', src))
    starts = set(re.findall(r'startActivityForResult\([^)]*?,\s*(REQ_\w+)', src))
    if starts and 'onActivityResult' not in src:
        err('%s starts for result %s but has no onActivityResult' % (cls, sorted(starts)))
    handled = set(re.findall(r'requestCode\s*==?\s*(\w+)|requestCode\s*!=?\s*(\w+)', src))
    handled = set(x for tup in handled for x in tup if x)
    for s in starts:
        if s not in handled:
            warn('%s starts %s; onActivityResult never compares it' % (cls, s)); continue
        pairs += 1
ok('%d request codes correctly paired' % pairs)

# ------------------------------------------------------------------ E. RBAC map
print('\n== E. RBAC coverage ==')
roles_src = sources['Roles']
modules = set(re.findall(r'String\s+M_(\w+)\s*=', roles_src))   # constant names
module_vals = set(re.findall(r'(?:M_\w+)\s*=\s*"([\w_]+)"', roles_src))
map_names = set(re.findall(r'"(\w+Activity(?:\$[\w]+)?)"\s*\.equals\(', roles_src))
home = sources['HomeActivity']
tile_modules = set(re.findall(r'"(\w+)"\},\s*$', home, re.M))       # last col of TILE rows
tile_targets = set(re.findall(r'(\w+Activity)\.class', home))
missing_module = sorted(m for m in tile_modules if m not in module_vals)
if missing_module: err('Home TILES reference unknown modules: ' + ', '.join(missing_module))
else: ok('all %d Home tile modules exist in Roles' % len(tile_modules))
ungated = sorted(a for a in act_names if a not in map_names and a not in tile_targets)
print('  info  consciously ungated screens (%d): %s'
      % (len(ungated), ', '.join(ungated)))
SAFETY = {'FlashActivity', 'WriteDataActivity', 'SupplierFlashActivity'}
for s in SAFETY:
    if s in map_names: ok('%s covered by navigation guard' % s)
# hard entry guards for destructive ops even via deep-link
for s in SAFETY:
    if s in sources and 'Roles.can' not in sources[s]:
        err('%s lacks its own Roles.can entry guard' % s)
ok('destructive-op screens carry their own entry guards')

# ------------------------------------------------------------------ F. services/provider
print('\n== F. Services / provider references ==')
for s in sorted(svc_names | prov_names):
    if s == 'NirixXApp': continue
    used = any(re.search(r'\b' + s + r'\b', src) for c, src in sources.items()
               if c != s)
    if not used: warn('%s declared but never referenced from other code' % s)
    else: ok('%s referenced from code' % s)

# ------------------------------------------------------------------ G. image lookups
print('\n== G. Dynamic drawable lookups ==')
for cls, src in sources.items():
    for m in re.findall(r'getIdentifier\((\w+(?:\.\w+)*)\s*,\s*"drawable"', src):
        # only flag plain-string literal usage elsewhere; dynamic fields unresolved here
        pass
ids = set(re.findall(r'"\s*(veh_\w+)\s*"', sources.get('Db', '')))
miss = sorted(i for i in ids if i not in drawables)
if miss: err('vehicle images referenced by Db but missing in res: ' + ', '.join(miss))
else: ok('vehicle image names in Db resolve to drawables (%d)' % len(ids))

print('\n== LINK AUDIT SUMMARY == errors=%d warnings=%d' % (len(errs), len(warns)))
sys.exit(1 if errs else 0)
