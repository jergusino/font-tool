#!/usr/bin/env python3
"""
add_missing_letters.py — build missing accented letters into a font.

Default target is Slovak (á ä č ď é í ĺ ľ ň ó ô ŕ š ť ú ý ž + capitals).
Every missing letter is assembled from parts the font already has, so the
accents match the font's own style:

  1. The accent is lifted from a letter that already carries it
     (the caron from Š/š, the acute from É/é, ...).
  2. If no such letter exists, the font's spacing accent is used (ˇ ´ ¨ ...).
  3. ď ľ ť and Ľ get the Slovak apostrophe-style caron, built from the
     font's own right quote (’).

The new letters get the base letter's spacing and kerning, are mapped in
cmap, and the output is a normal .ttf or .otf (same format as the input).

Usage:
  python3 add_missing_letters.py Font.ttf                    -> Font-SK.ttf
  python3 add_missing_letters.py Font.otf -o Fixed.otf
  python3 add_missing_letters.py Font.ttf --charset czech
  python3 add_missing_letters.py Font.ttf --chars "ŕĺ"       only these letters
  python3 add_missing_letters.py Font.ttf --preview check.png
  python3 add_missing_letters.py *.ttf --out-dir fixed/      several fonts at once

Options:
  --charset slovak|czech|ce   which letters to make sure exist (default slovak)
  --chars TEXT                exact list of letters instead of a charset
  --lcaron caron|apostrophe   style of capital Ľ (default apostrophe)
  --apostrophe-scale 0.9      size of the apostrophe-caron relative to ’
  --rename "Family SK"        give the font a new family name (install both side by side)
  --raise-win-ascent          raise OS/2 winAscent so tall new capitals are not
                              clipped in old Windows apps (changes line spacing there)
  --no-kerning                do not copy kerning from the base letters
  --preview FILE.png          render a before/after sample

Requires: pip install fonttools  (and pillow for --preview)
Not supported: variable fonts, CFF2, CID-keyed CFF, letters with marks below
or through the base (ą ę ł đ ...); those are listed as skipped.

Check the font licence before modifying it: many licences forbid edits.
"""

import argparse
import copy
import math
import sys
import unicodedata
from pathlib import Path

from fontTools.agl import UV2AGL
from fontTools.pens.basePen import BasePen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen, RecordingPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

# ---------------------------------------------------------------- character sets

SLOVAK = "áäčďéíĺľňóôŕšťúýžÁÄČĎÉÍĹĽŇÓÔŔŠŤÚÝŽ"
CZECH = "áčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ"
EXTRA_CE = "ćńśźżőűĆŃŚŹŻŐŰ"  # Polish / Hungarian letters with marks above


def _uniq(s):
    return "".join(dict.fromkeys(s))


CHARSETS = {
    "slovak": SLOVAK,
    "czech": CZECH,
    "ce": _uniq(SLOVAK + CZECH + EXTRA_CE),
}

# combining mark -> spacing / combining glyphs that can serve as a fallback source
MARK_FALLBACKS = {
    "́": ["´", "ˊ", "́"],  # acute
    "̌": ["ˇ", "̌"],  # caron
    "̂": ["ˆ", "̂"],  # circumflex
    "̈": ["¨", "̈"],  # diaeresis
    "̊": ["˚", "̊"],  # ring
    "̋": ["˝", "̋"],  # double acute
    "̇": ["˙", "̇"],  # dot above
    "̀": ["`", "ˋ", "̀"],  # grave
}
APOSTROPHE_CARON = set("ďľť")  # + Ľ unless --lcaron caron
# bases whose accent makes the best donor, most preferred first
DONOR_ORDER = "SZCENRAOUYDTGKLHWsznceraouydtgklhw"


# ---------------------------------------------------------------- geometry helpers


class FlattenPen(BasePen):
    """Turns one contour into a polyline (curves sampled), for measuring."""

    def __init__(self, glyphSet=None, steps=16):
        super().__init__(glyphSet)
        self.pts = []
        self.steps = steps

    def _moveTo(self, p):
        self.pts.append(p)

    def _lineTo(self, p):
        self.pts.append(p)

    def _curveToOne(self, p1, p2, p3):
        p0 = self._getCurrentPoint()
        for i in range(1, self.steps + 1):
            t = i / self.steps
            mt = 1 - t
            self.pts.append(
                (
                    mt**3 * p0[0] + 3 * mt * mt * t * p1[0] + 3 * mt * t * t * p2[0] + t**3 * p3[0],
                    mt**3 * p0[1] + 3 * mt * mt * t * p1[1] + 3 * mt * t * t * p2[1] + t**3 * p3[1],
                )
            )

    def _qCurveToOne(self, p1, p2):
        p0 = self._getCurrentPoint()
        for i in range(1, self.steps + 1):
            t = i / self.steps
            mt = 1 - t
            self.pts.append(
                (
                    mt * mt * p0[0] + 2 * mt * t * p1[0] + t * t * p2[0],
                    mt * mt * p0[1] + 2 * mt * t * p1[1] + t * t * p2[1],
                )
            )

    def _closePath(self):
        pass

    def _endPath(self):
        pass


class Contour:
    """One closed contour: its drawing ops, a flattened polygon and its bounds."""

    def __init__(self, ops):
        self.ops = ops
        fp = FlattenPen()
        RecordingPen.replay(_rec(ops), fp)
        self.poly = fp.pts
        xs = [p[0] for p in self.poly] or [0]
        ys = [p[1] for p in self.poly] or [0]
        self.bounds = (min(xs), min(ys), max(xs), max(ys))


def _rec(ops):
    r = RecordingPen()
    r.value = list(ops)
    return r


def contours_of(font, glyph_name):
    """Decomposed outline of a glyph, split into Contour objects."""
    gs = font.getGlyphSet()
    pen = DecomposingRecordingPen(gs)
    gs[glyph_name].draw(pen)
    out, cur = [], []
    for op in pen.value:
        cur.append(op)
        if op[0] in ("closePath", "endPath"):
            out.append(Contour(cur))
            cur = []
    if cur:
        out.append(Contour(cur))
    return out


def bounds_of(cs):
    if not cs:
        return None
    return (
        min(c.bounds[0] for c in cs),
        min(c.bounds[1] for c in cs),
        max(c.bounds[2] for c in cs),
        max(c.bounds[3] for c in cs),
    )


def ink_span(cs, frac, top=True):
    """Horizontal extent of the ink in the top (or bottom) `frac` of the outline.
    Used to find where an accent should sit: over the stem of L, over the bar of T..."""
    b = bounds_of(cs)
    h = b[3] - b[1]
    xs = []
    for k in range(6):
        d = h * (0.02 + (frac - 0.02) * k / 5)
        y = b[3] - d if top else b[1] + d
        for c in cs:
            pts = c.poly
            n = len(pts)
            for i in range(n):
                (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % n]
                if (y1 <= y < y2) or (y2 <= y < y1):
                    xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
    if not xs:
        return b[0], b[2]
    return min(xs), max(xs)


def split_top_cluster(cs):
    """Split a glyph into (top group, rest) at the highest vertical gap.
    For Š this returns (caron, S); for é (acute, e); for i (dot, stem)."""
    order = sorted(cs, key=lambda c: -c.bounds[3])
    group = [order[0]]
    low = order[0].bounds[1]
    for c in order[1:]:
        if c.bounds[3] >= low - 1:
            group.append(c)
            low = min(low, c.bounds[1])
        else:
            break
    rest = [c for c in cs if c not in group]
    return group, rest


def transformed_ops(cs, m):
    """Drawing ops of contours after an affine transform m=(xx,xy,yx,yy,dx,dy)."""
    rec = RecordingPen()
    tp = TransformPen(rec, m)
    for c in cs:
        RecordingPen.replay(_rec(c.ops), tp)
    return rec.value


# ---------------------------------------------------------------- the patcher


class Patcher:
    def __init__(self, font, args):
        self.f = font
        self.a = args
        self.upm = font["head"].unitsPerEm
        self.cmap = font.getBestCmap()
        self.is_cff = "CFF " in font
        self.order = list(font.getGlyphOrder())
        self.new = []  # (char, glyph_name, base_glyph, copy_left, copy_right)
        self.report = []
        # lowercase/caps reference heights
        self.xh = self._top_of("x") or self._top_of("o") or 0.5 * self.upm
        self.asc = self._top_of("l") or self._top_of("d") or 0.75 * self.upm

    # -- lookups

    def gname(self, ch):
        return self.cmap.get(ord(ch))

    def _top_of(self, ch):
        g = self.gname(ch)
        if not g:
            return None
        b = bounds_of(contours_of(self.f, g))
        return b[3] if b else None

    def base_contours(self, base):
        """Outline of the base letter. For i/j the dot is removed."""
        if base in "ij":
            dotless = self.gname("ı" if base == "i" else "ȷ")
            if dotless:
                return contours_of(self.f, dotless), dotless
            g = self.gname(base)
            if not g:
                return None, None
            cs = contours_of(self.f, g)
            if len(cs) > 1:
                _, rest = split_top_cluster(cs)
                return rest, g
            return cs, g
        g = self.gname(base)
        if not g:
            return None, None
        return contours_of(self.f, g), g

    # -- accent sources

    def donor_mark(self, mark, upper):
        """Find the mark in an existing precomposed letter.
        Returns (mark contours, offset from base anchor, gap above base, donor char, same case?)."""
        cands = []
        for cp in self.cmap:
            ch = chr(cp)
            nfd = unicodedata.normalize("NFD", ch)
            if len(nfd) != 2 or nfd[1] != mark or not nfd[0].isalpha():
                continue
            if ch in APOSTROPHE_CARON or ch == "Ľ":  # their caron is an apostrophe
                continue
            if nfd[0] in "ijIJ":
                pri = 90
            else:
                pri = DONOR_ORDER.find(nfd[0])
                pri = 80 if pri < 0 else pri % 17
            same = ch.isupper() == upper
            cands.append((0 if same else 1, pri, ch))
        for same_rank, _, ch in sorted(cands):
            cs = contours_of(self.f, self.cmap[ord(ch)])
            if len(cs) < 2:
                continue
            group, rest = split_top_cluster(cs)
            if not rest:
                continue
            mb, rb = bounds_of(group), bounds_of(rest)
            gap = mb[1] - rb[3]
            if gap <= 0 or (mb[3] - mb[1]) > 0.6 * (rb[3] - rb[1]):
                continue
            ax0, ax1 = ink_span(rest, 0.2)
            offset = (mb[0] + mb[2]) / 2 - (ax0 + ax1) / 2
            return group, offset, gap, ch, same_rank == 0
        return None

    def spacing_mark(self, mark, upper):
        for alt in MARK_FALLBACKS.get(mark, []):
            g = self.gname(alt)
            if not g:
                continue
            cs = contours_of(self.f, g)
            if not cs:
                continue
            mb = bounds_of(cs)
            gap = mb[1] - self.xh  # spacing accents are drawn for lowercase
            gap = min(max(gap, 0.03 * self.upm), 0.25 * self.upm)
            return cs, 0.0, gap, alt, not upper
        return None

    # -- building

    def build_regular(self, ch, base, mark):
        upper = ch.isupper()
        bcs, bname = self.base_contours(base)
        if not bcs:
            return None, f"no base letter '{base}' in the font"
        src = self.donor_mark(mark, upper) or self.spacing_mark(mark, upper)
        if not src:
            return None, "no letter or accent glyph to take the accent from"
        mcs, offset, gap, donor, same_case = src
        mb = bounds_of(mcs)
        tb = bounds_of(bcs)
        ax0, ax1 = ink_span(bcs, 0.2)
        target_cx = (ax0 + ax1) / 2 + offset
        # keep the accent at the donor's height when the base is no taller,
        # otherwise lift it to keep the same gap above the base
        new_y0 = tb[3] + gap
        if same_case:
            new_y0 = max(new_y0, mb[1])
        dx = target_cx - (mb[0] + mb[2]) / 2
        dy = new_y0 - mb[1]
        ops = transformed_ops(bcs, (1, 0, 0, 1, 0, 0)) + transformed_ops(mcs, (1, 0, 0, 1, dx, dy))
        adv = self.f["hmtx"][bname][0]
        how = f"accent from {donor}" if len(donor) == 1 and donor.isalpha() else f"accent from spacing glyph U+{ord(donor):04X}"
        return (ops, adv, bname, True, True), how

    def build_apostrophe(self, ch, base):
        bcs, bname = self.base_contours(base)
        if not bcs:
            return None, f"no base letter '{base}' in the font"
        q = self.gname("’") or self.gname("'")
        if not q:
            return None, "no apostrophe glyph"
        qcs = contours_of(self.f, q)
        s = self.a.apostrophe_scale
        qb = bounds_of(qcs)
        qw, qh = (qb[2] - qb[0]) * s, (qb[3] - qb[1]) * s
        tb = bounds_of(bcs)
        sx0, sx1 = ink_span(bcs, 0.1)  # the top of the stem
        top = tb[3]
        if base == "t":
            top = max(top, self.asc)
        gap_x = max(0.015 * self.upm, 0.12 * qw)
        # align by the left edge of the upper part of the ’ (matters for slanted fonts,
        # where the bottom of the mark sits much further left than its top)
        qtop_left = ink_span(qcs, 0.35)[0] * s
        dx = sx1 + gap_x - qtop_left
        dy = top - qb[3] * s
        ops = transformed_ops(bcs, (1, 0, 0, 1, 0, 0)) + transformed_ops(qcs, (s, 0, 0, s, dx, dy))
        adv = self.f["hmtx"][bname][0]
        mark_right = qb[2] * s + dx
        rsb = adv - tb[2]  # may be negative in connected scripts: keep the same overhang
        new_adv = max(adv, math.ceil(mark_right + rsb))
        _ = qh
        return (ops, new_adv, bname, False, True), "apostrophe-style caron from ’"

    def glyph_name_for(self, ch):
        cp = ord(ch)
        for name in (UV2AGL.get(cp), "uni%04X" % cp):
            if name and name not in self.order:
                return name, False
        # a glyph with the standard name exists already
        for name in (UV2AGL.get(cp), "uni%04X" % cp):
            if name and name in self.order and name not in self.cmap.values():
                return name, True
        name = "uni%04X.sk" % cp
        i = 1
        while name in self.order:
            name = "uni%04X.sk%d" % (cp, i)
            i += 1
        return name, False

    def add_glyph(self, name, ops, adv, base_name):
        bp = BoundsPen(None)
        RecordingPen.replay(_rec(ops), bp)
        b = bp.bounds or (0, 0, 0, 0)
        lsb = int(round(b[0]))
        if self.is_cff:
            cff = self.f["CFF "].cff
            td = cff.topDictIndex[0]
            pen = T2CharStringPen(adv, None)
            RecordingPen.replay(_rec(ops), pen)
            cs = pen.getCharString(private=td.Private, globalSubrs=cff.GlobalSubrs)
            strings = td.CharStrings
            strings.charStringsIndex.append(cs)
            strings.charStrings[name] = len(strings.charStringsIndex) - 1
            td.charset.append(name)
        else:
            pen = TTGlyphPen(None)
            RecordingPen.replay(_rec(ops), pen)
            g = pen.glyph()
            glyf = self.f["glyf"]
            glyf[name] = g
            g.recalcBounds(glyf)
            lsb = g.xMin if hasattr(g, "xMin") else 0
        self.f["hmtx"][name] = (int(adv), int(lsb))
        if "vmtx" in self.f and base_name in self.f["vmtx"].metrics:
            self.f["vmtx"][name] = self.f["vmtx"][base_name]
        if name not in self.order:
            self.order.append(name)
        return b

    def map_cmap(self, ch, name):
        for t in self.f["cmap"].tables:
            if t.isUnicode() and (t.format != 4 or ord(ch) < 0x10000):
                t.cmap[ord(ch)] = name
        self.cmap[ord(ch)] = name

    # -- main

    def run(self, chars):
        tall = 0
        for ch in chars:
            if ord(ch) in self.cmap:
                continue
            nfd = unicodedata.normalize("NFD", ch)
            name, exists = self.glyph_name_for(ch)
            if exists:
                self.map_cmap(ch, name)
                self.report.append((ch, "mapped", f"glyph '{name}' was in the font but had no code point"))
                continue
            if len(nfd) != 2 or nfd[1] not in MARK_FALLBACKS:
                self.report.append((ch, "skipped", "mark below or through the letter is not supported"))
                continue
            base, mark = nfd
            apos = ch in APOSTROPHE_CARON or (ch == "Ľ" and self.a.lcaron == "apostrophe")
            built, how = self.build_apostrophe(ch, base) if apos else self.build_regular(ch, base, mark)
            if not built and apos:  # no apostrophe in the font: fall back to a normal caron
                built, how = self.build_regular(ch, base, mark)
            if not built:
                self.report.append((ch, "skipped", how))
                continue
            ops, adv, base_name, copy_left, copy_right = built
            b = self.add_glyph(name, ops, adv, base_name)
            tall = max(tall, b[3])
            self.map_cmap(ch, name)
            self.new.append((ch, name, base_name, copy_left, copy_right))
            self.report.append((ch, "built", how))

        if not self.new and not any(r[1] == "mapped" for r in self.report):
            return
        self.f.setGlyphOrder(self.order)
        if self.is_cff:
            self.f["CFF "].cff.topDictIndex[0].charset = list(self.order)
        if "GDEF" in self.f:
            gdef = self.f["GDEF"].table
            if getattr(gdef, "GlyphClassDef", None):
                for _, name, *_ in self.new:
                    gdef.GlyphClassDef.classDefs[name] = 1
        if not self.a.no_kerning:
            self.copy_kerning()
        self.update_os2(tall)
        for tag in ("DSIG", "hdmx", "LTSH", "VDMX"):  # per-glyph or signature tables that would be stale
            if tag in self.f:
                del self.f[tag]

    # -- kerning

    def copy_kerning(self):
        n = 0
        if "GPOS" in self.f:
            gpos = self.f["GPOS"].table
            for lookup in gpos.LookupList.Lookup if gpos.LookupList else []:
                for st in lookup.SubTable:
                    if lookup.LookupType == 9:
                        if st.ExtensionLookupType != 2:
                            continue
                        st = st.ExtSubTable
                    elif lookup.LookupType != 2:
                        continue
                    n += self._kern_subtable(st)
        if "kern" in self.f:
            for t in self.f["kern"].kernTables:
                if not hasattr(t, "kernTable"):
                    continue
                add = {}
                for (l, r), v in t.kernTable.items():
                    for _, name, base, cl, cr in self.new:
                        if cl and l == base:
                            add[(name, r)] = v
                        if cr and r == base:
                            add[(l, name)] = v
                t.kernTable.update(add)
                n += len(add)
        self.kern_pairs = n

    def _kern_subtable(self, st):
        n = 0
        if st.Format == 1:
            cov = st.Coverage.glyphs
            for _, name, base, cl, cr in self.new:
                if cr:
                    for ps in st.PairSet:
                        recs = [r for r in ps.PairValueRecord if r.SecondGlyph == base]
                        for r in recs:
                            r2 = copy.deepcopy(r)
                            r2.SecondGlyph = name
                            ps.PairValueRecord.append(r2)
                            n += 1
                        ps.PairValueCount = len(ps.PairValueRecord)
                if cl and base in cov and name not in cov:
                    ps = copy.deepcopy(st.PairSet[cov.index(base)])
                    cov.append(name)
                    st.PairSet.append(ps)
                    st.PairSetCount = len(st.PairSet)
                    n += len(ps.PairValueRecord)
        elif st.Format == 2:
            cov = st.Coverage.glyphs
            for _, name, base, cl, cr in self.new:
                if cl and base in cov and name not in cov:
                    cov.append(name)
                    c = st.ClassDef1.classDefs.get(base)
                    if c:
                        st.ClassDef1.classDefs[name] = c
                    n += 1
                if cr:
                    c = st.ClassDef2.classDefs.get(base)
                    if c:
                        st.ClassDef2.classDefs[name] = c
                        n += 1
        return n

    # -- metadata

    def update_os2(self, tall):
        if "OS/2" not in self.f:
            return
        os2 = self.f["OS/2"]
        cps = [ord(c) for c, *_ in self.new]
        if any(0x80 <= c <= 0xFF for c in cps):
            os2.ulUnicodeRange1 |= 1 << 1
        if any(0x100 <= c <= 0x17F for c in cps):
            os2.ulUnicodeRange1 |= 1 << 2
        if os2.version >= 1 and all(ord(c) in self.cmap for c in SLOVAK):
            os2.ulCodePageRange1 |= 1 << 1  # Latin 2 (Central Europe, cp1250)
        self.tall = tall
        if tall > os2.usWinAscent:
            if self.a.raise_win_ascent:
                os2.usWinAscent = int(math.ceil(tall))
                self.report.append(("", "note", f"winAscent raised to {os2.usWinAscent}"))
            else:
                self.report.append(
                    (
                        "",
                        "note",
                        f"the tallest new letter reaches {int(tall)} units, above winAscent ({os2.usWinAscent}). "
                        "Old Windows apps may clip its accent; browsers, Adobe apps and Remotion do not. "
                        "Use --raise-win-ascent to fix (this changes line spacing in those apps).",
                    )
                )


# ---------------------------------------------------------------- naming


def rename(font, family):
    name = font["name"]
    sub = name.getDebugName(17) or name.getDebugName(2) or "Regular"
    old_family = name.getDebugName(16) or name.getDebugName(1)
    ps = family.replace(" ", "") + "-" + sub.replace(" ", "")
    full = family if sub == "Regular" else f"{family} {sub}"
    for rec in name.names:
        if rec.nameID in (1, 16):
            rec.string = family
        elif rec.nameID == 4:
            rec.string = full
        elif rec.nameID == 6:
            rec.string = ps
        elif rec.nameID == 3:
            rec.string = f"{ps};patched"
    if "CFF " in font:
        cff = font["CFF "].cff
        td = cff.topDictIndex[0]
        cff.fontNames[0] = ps
        if hasattr(td, "FamilyName"):
            td.FamilyName = family
        if hasattr(td, "FullName"):
            td.FullName = full
    return old_family


# ---------------------------------------------------------------- preview


SAMPLE = [
    "Kŕdeľ šťastných ďatľov učí pri ústí",
    "Váhu mĺkveho koňa obhrýzať kôru a žrať čerstvé mäso.",
    "ÁÄČĎÉÍĹĽŇÓÔŔŠŤÚÝŽ  áäčďéíĺľňóôŕšťúýž",
    "ŤAŽKÝ ĽAD · ĎAKUJEM · ČIERNA · ŇUFKO · ĹÍŇ",
]


def preview(orig_path, new_path, out_png, chars):
    from PIL import Image, ImageDraw, ImageFont

    W, size, pad = 1800, 64, 30
    lines = SAMPLE if set(chars) <= set(SLOVAK) else SAMPLE[:0] + [chars]
    blocks = [("original", orig_path), ("patched", new_path)]
    H = pad + len(blocks) * (36 + len(lines) * int(size * 1.5) + pad)
    img = Image.new("RGB", (W, H), "#060909")
    d = ImageDraw.Draw(img)
    label = ImageFont.load_default()
    y = pad
    for title, path in blocks:
        d.text((pad, y), f"{title}: {Path(path).name}", fill="#FFC600", font=label)
        y += 36
        font = ImageFont.truetype(str(path), size)
        for line in lines:
            d.text((pad, y), line, fill="#FAF1D6", font=font)
            y += int(size * 1.5)
        y += pad
    img.save(out_png)


# ---------------------------------------------------------------- CLI


def process(src, dst, args, chars):
    font = TTFont(src)
    if "fvar" in font:
        sys.exit(f"{src}: variable fonts are not supported")
    if "CFF2" in font:
        sys.exit(f"{src}: CFF2 fonts are not supported")
    if "CFF " in font and hasattr(font["CFF "].cff.topDictIndex[0], "ROS"):
        sys.exit(f"{src}: CID-keyed CFF fonts are not supported")
    if "GPOS" in font:
        font["GPOS"].table  # decompile before the glyph order changes
    p = Patcher(font, args)
    p.run(chars)

    print(f"\n{Path(src).name}")
    if not p.report:
        print("  nothing to do: every letter is already in the font")
    for ch, status, how in p.report:
        print(f"  {ch:2} {status:8} {how}" if ch else f"  note: {how}")
    if args.rename:
        old = rename(font, args.rename)
        print(f"  renamed family '{old}' -> '{args.rename}'")

    font.save(dst)

    # verify the result opens and has every letter
    check = TTFont(dst)
    cmap = check.getBestCmap()
    missing = [c for c in chars if ord(c) not in cmap]
    print(f"  saved {dst}  ({len(check.getGlyphOrder())} glyphs"
          + (f", {getattr(p, 'kern_pairs', 0)} kerning entries copied" if p.new and not args.no_kerning else "")
          + ")")
    if missing:
        print("  still missing:", "".join(missing))
    if args.preview:
        out = args.preview if len(args.fonts) == 1 else str(Path(dst).with_suffix(".preview.png"))
        preview(src, dst, out, chars)
        print(f"  preview {out}")


def main():
    ap = argparse.ArgumentParser(description="Build missing accented letters (Slovak by default) into a font.")
    ap.add_argument("fonts", nargs="+", help=".ttf or .otf file(s)")
    ap.add_argument("-o", "--output", help="output file (single input only)")
    ap.add_argument("--out-dir", help="folder for outputs (several inputs)")
    ap.add_argument("--charset", choices=sorted(CHARSETS), default="slovak")
    ap.add_argument("--chars", help="exact letters to ensure, overrides --charset")
    ap.add_argument("--lcaron", choices=["apostrophe", "caron"], default="apostrophe", help="style of capital Ľ")
    ap.add_argument("--apostrophe-scale", type=float, default=0.9)
    ap.add_argument("--rename", help="new family name")
    ap.add_argument("--raise-win-ascent", action="store_true")
    ap.add_argument("--no-kerning", action="store_true")
    ap.add_argument("--preview", help="before/after PNG")
    args = ap.parse_args()

    if args.output and len(args.fonts) > 1:
        sys.exit("-o works with one input; use --out-dir for several")
    chars = _uniq(args.chars) if args.chars else CHARSETS[args.charset]

    for src in args.fonts:
        sp = Path(src)
        if args.output:
            dst = Path(args.output)
        else:
            folder = Path(args.out_dir) if args.out_dir else sp.parent
            folder.mkdir(parents=True, exist_ok=True)
            dst = folder / f"{sp.stem}-SK{sp.suffix}"
        process(str(sp), str(dst), args, chars)


if __name__ == "__main__":
    main()
