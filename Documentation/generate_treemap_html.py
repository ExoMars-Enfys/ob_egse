import json
from pathlib import Path
from collections import defaultdict

# Color palette for package blocks
PKG_COLORS = ["#cde7ff", "#d8f6df", "#ffe7c2", "#e8ddff", "#ffd9dc", "#e9eef7"]

# Order for main package blocks
PKG_ORDER = ["core_modules", "utility_modules", "widget_modules", "analysis_modules", "scripts_modules", "root"]


def load_metadata(json_path):
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


def group_by_package(modules):
    pkgs = defaultdict(list)
    for m in modules:
        pkgs[m["package"]].append(m)
    return pkgs


def html_escape(text):
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_treemap(pkgs):
    html = ["<div class='tree'>"]
    for i, pkg in enumerate(PKG_ORDER):
        mods = pkgs.get(pkg, [])
        if not mods:
            continue
        color = PKG_COLORS[i % len(PKG_COLORS)]
        html.append(
            f"<section class='pkg' style='--pkg-color:{color}; flex:{max(4, len(mods))}'><h3>{pkg}</h3><div class='mods'>"
        )
        for m in mods:
            fn_count = len(m["functions"])
            cls_count = len(m["classes"])
            mod_id = m["path"].replace("/", "__").replace(".py", "_py")
            html.append(
                f"<a class='mod' href='#{mod_id}' title='{m['path']}'><span class='mod-name'>{m['module']}</span><span class='mod-meta'>{fn_count} fn, {cls_count} cls</span></a>"
            )
        html.append("</div></section>")
    html.append("</div>")
    return "\n".join(html)


def render_details(modules):
    html = []
    for m in modules:
        mod_id = m["path"].replace("/", "__").replace(".py", "_py")
        html.append(
            f"<article id='{mod_id}' class='detail'><h4>{m['module']}</h4><p class='path'>{m['path']}</p><p>{html_escape(m['description'])}</p><ul>"
        )
        if not m["functions"] and not m["classes"]:
            html.append("<li>No methods/functions documented for this module.</li>")
        for fn in m["functions"]:
            html.append(
                f"<li><b>{fn['name']}</b> <span class='chip'>function</span><br>{html_escape(fn['description'])}</li>"
            )
        for cls in m["classes"]:
            html.append(
                f"<li><b>{cls['name']}</b> <span class='chip'>class</span><br>{html_escape(cls['description'])}</li>"
            )
            for method in cls.get("methods", []):
                html.append(
                    f"<li class='method'><b>{cls['name']}.{method['name']}</b> <span class='chip'>method</span><br>{html_escape(method['description'])}</li>"
                )
        html.append("</ul></article>")
    return "\n".join(html)


def main():
    meta_path = Path(__file__).parent / "Documentation" / "module_metadata.json"
    out_path = Path(__file__).parent / "Documentation" / "INTERACTIVE_MODULE_TREEMAP.html"
    meta = load_metadata(meta_path)
    modules = meta["modules"]
    pkgs = group_by_package(modules)
    # HTML skeleton
    html = f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>OB EGSE Project Treemap</title>
<style>
body {{ margin:0; font-family:Segoe UI, Tahoma, sans-serif; background:#f4f7fb; color:#122036; }}
.wrap {{ padding:14px; display:grid; grid-template-columns:1.4fr 1fr; gap:14px; min-height:100vh; }}
.panel {{ background:#fff; border:1px solid #d5deea; border-radius:14px; box-shadow:0 10px 28px rgba(19,32,51,.08); overflow:hidden; }}
.head {{ padding:12px 14px; border-bottom:1px solid #d5deea; }}
.head h1 {{ margin:0; font-size:20px; }} .sub {{ margin:4px 0 0; color:#5f6f86; font-size:13px; }}
.tree {{ padding:10px; display:flex; gap:8px; align-items:stretch; min-height:72vh; overflow:auto; }}
.pkg {{ background:var(--pkg-color); border:1px solid #fff; border-radius:8px; padding:8px; display:flex; flex-direction:column; min-width:150px; }}
.pkg h3 {{ margin:0 0 8px; font-size:13px; }}
.mods {{ display:grid; gap:6px; }}
.mod {{ display:block; text-decoration:none; color:#122036; background:rgba(255,255,255,.45); border:1px solid rgba(18,32,54,.08); border-radius:6px; padding:6px; }}
.mod:hover {{ background:rgba(255,255,255,.7); }}
.mod-name {{ display:block; font-weight:600; font-size:12px; }}
.mod-meta {{ display:block; font-size:11px; color:#4f5f76; margin-top:2px; }}
.details {{ padding:10px; max-height:82vh; overflow:auto; }}
.hint {{ font-size:13px; color:#5f6f86; background:#f8fbff; border:1px solid #d5deea; border-radius:8px; padding:8px; margin-bottom:10px; }}
.detail {{ display:none; border:1px solid #d5deea; border-radius:10px; padding:10px; margin-bottom:10px; background:#fbfdff; }}
.detail:target {{ display:block; }}
.detail h4 {{ margin:0 0 6px; font-size:16px; }}
.path {{ margin:0 0 8px; font-size:12px; color:#5f6f86; }}
.detail ul {{ margin:8px 0 0 18px; padding:0; }}
.detail li {{ margin:6px 0; font-size:13px; line-height:1.4; }}
.method {{ margin-left:10px; }}
.chip {{ font-size:11px; border:1px solid #d5deea; border-radius:999px; padding:1px 6px; color:#4f5f76; }}
@media (max-width:1100px) {{ .wrap {{ grid-template-columns:1fr; }} .tree {{ min-height:48vh; }} }}
</style>
</head>
<body>
<div class='wrap'>
  <section class='panel'>
    <div class='head'>
      <h1>Project Flow Treemap</h1>
      <p class='sub'>Regenerated from current src state. Top is main entrypoint conceptually, then package blocks, then module tiles.</p>
    </div>
    {render_treemap(pkgs)}
  </section>
  <aside class='panel'>
    <div class='head'>
      <h1>Selected Module</h1>
      <p class='sub'>Method and class details by module.</p>
    </div>
    <div class='details'>
      <div class='hint'>Click any module tile on the left. This is static HTML so it does not depend on scripts or CDN.</div>
      {render_details(modules)}
    </div>
  </aside>
</div>
</body>
</html>"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
