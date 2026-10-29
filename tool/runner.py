"""Browser glue for font_tool.py (runs inside Pyodide on the tool page).

font_tool.py is used exactly as written: its own process() checks, patches,
saves and verifies the font. This file only passes the options from the page
and hands the result back as JSON.
"""
import io
import json
import types
import unicodedata
from contextlib import redirect_stdout
from pathlib import Path

from fontTools.ttLib import TTFont

import font_tool as ft

_last = {}


class _CapturingPatcher(ft.Patcher):
    """Same Patcher, it just remembers itself so the page can show its report."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        _last["patcher"] = self


ft.Patcher = _CapturingPatcher


def fix_font(src, options_json):
    o = json.loads(options_json)
    args = types.SimpleNamespace(
        fonts=[src],
        output=None,
        out_dir=None,
        charset=o.get("charset") if o.get("charset") in ft.CHARSETS else "slovak",
        chars=(o.get("chars") or "").strip() or None,
        lcaron="caron" if o.get("lcaron") == "caron" else "apostrophe",
        apostrophe_scale=float(o.get("apostrophe_scale") or 0.9),
        rename=(o.get("rename") or "").strip() or None,
        raise_win_ascent=bool(o.get("raise_win_ascent")),
        no_kerning=not o.get("kerning", True),
        preview=None,
    )
    chars = ft._uniq(unicodedata.normalize("NFC", args.chars)) if args.chars else ft.CHARSETS[args.charset]
    sp = Path(src)
    dst = str(sp.with_name(f"{sp.stem}-SK{sp.suffix}"))

    _last.clear()
    log = io.StringIO()
    try:
        with redirect_stdout(log):
            ft.process(src, dst, args, chars)
    except SystemExit as e:
        msg = str(e.code if e.code is not None else e)
        return json.dumps({"ok": False, "error": msg.replace(src + ": ", ""), "log": log.getvalue()})
    except Exception as e:  # a font the script can't read
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}", "log": log.getvalue()})

    p = _last.get("patcher")
    report = [{"char": c, "status": s, "how": h} for c, s, h in (p.report if p else [])]
    cmap = TTFont(dst).getBestCmap()
    return json.dumps(
        {
            "ok": True,
            "output": dst,
            "name": Path(dst).name,
            "changed": bool(p and (p.new or any(r["status"] == "mapped" for r in report))),
            "report": report,
            "missing": "".join(c for c in chars if ord(c) not in cmap),
            "chars": chars,
            "sample": ft.SAMPLE if set(chars) <= set(ft.SLOVAK) else [chars],
            "log": log.getvalue(),
        }
    )
