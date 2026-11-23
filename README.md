# Jergušino Font Tool

Two pages, published with GitHub Pages at jergusino.com/font-tool/:

- `index.html` (jergusino.com/font-tool/): leave your email, get the tool by email.
  The link is mailed after the address is confirmed.
- `tool/` (jergusino.com/font-tool/tool/): the tool itself. Upload a .ttf or .otf, it builds
  the missing Slovak (or Czech / Central European) letters from the font's own parts,
  shows a before/after preview and gives back the fixed font to download.

## How the tool works

`tool/font_tool.py` is the original Python script, unchanged. The page runs it in the
browser with [Pyodide](https://pyodide.org) (Python + fontTools compiled for the web),
so fonts never leave the visitor's computer. `tool/runner.py` only passes the page's
options to the script's own `process()` and returns its report.

To update the tool, replace `tool/font_tool.py` with a new version of the script.
The first run downloads Pyodide (about 10 MB) from cdn.jsdelivr.net; after that the
browser caches it.

## The email

The form posts `list=font-tool` to the `jergusino-mail` Cloudflare Worker at `https://api.jergusino.com/subscribe` (code and setup: `tools/mail-worker/` in the jergusino.github.io repo). It sends mail through Brevo from noreply@jergusino.com and stores signups in its D1 database. The Worker mails a confirm link; after the click it mails the link to jergusino.com/font-tool/tool/ and shows it on the confirm page. The freebie text lives in `LISTS` in the Worker.

## Licences

The page's fonts (Bricolage Grotesque, DM Mono) are open source (SIL OFL).
