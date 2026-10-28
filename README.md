# Jergusino signup page

A one-page signup site for the Jergusino newsletter, published with GitHub Pages.
Each email is added to a private Google Sheet ("Newsletter signups" in Google Drive).
Download it as Excel anytime: File → Download → Microsoft Excel (.xlsx).

## Connect the page to the sheet (about 3 minutes, once)

1. Open the **Newsletter signups** sheet in Google Drive.
2. **Extensions → Apps Script.** Delete what's there, paste the contents of
   [`apps-script/Code.gs`](apps-script/Code.gs), and save.
3. **Deploy → New deployment → ⚙ → Web app.**
   - Execute as: **Me**
   - Who has access: **Anyone**
4. Click **Deploy**, allow the permissions Google asks for, and copy the **Web app URL**
   (ends in `/exec`).
5. In `index.html`, set `const SHEET_URL = "…/exec";` and commit.

"Anyone" only lets people *add* a row through the page. Nobody can read the sheet
unless you share it.

Until `SHEET_URL` is set, the button shows "Signups open soon."

## Design

The page is part of the main site (jergusino.github.io / jergusino.com): same header with
the logo, same footer, Slovak copy.

- `assets/css/main.css` is a copy of the main site's stylesheet. If the main site's look
  changes, copy its `assets/css/main.css` here again. `assets/css/newsletter.css` adds the form.
- `assets/fonts/` and `assets/img/wordmark.svg` are the main site's fonts and logo.
- Links in the menu (`/`, `/projects/`) point to the main site.

Licences: Borisna is a demo font, free for private, non-profit use only. Before you sell
anything through this list, buy the commercial licence from Koplexs Studio.
Check that your Slithen and Edwardian Script licences cover web use.
