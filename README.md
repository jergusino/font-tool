# Jergušino Font Tool

Two pages, published with GitHub Pages at jergusino.com/font-tool/:

- `index.html` (jergusino.com/font-tool/): leave your email, get the tool by email.
  Every signup gets the link, whether or not the address is already in the sheet.
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

The form posts to the same Google Apps Script as the newsletter (`apps-script/Code.gs`,
same file as in the newsletter repo), with `list=font-tool`. The script:

- writes the signup into the **Subscribers** tab of the "Newsletter signups" sheet, with
  **List** = `font-tool` (once per address; newsletter subscribers have `newsletter`),
- emails the link to jergusino.com/font-tool/tool/ straight away, every time it is asked for,
  even if the address is already in the sheet (no confirmation step).

After changing `Code.gs`, paste it into Apps Script and deploy a **New version**
(Deploy → Manage deployments → pencil → Version: New version).

## Licences

Borisna is a demo font, free for private, non-profit use only. Check that your Slithen
and Edwardian Script licences cover web use.
