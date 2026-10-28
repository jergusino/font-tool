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

## Use your own display font

The page uses Anton as a stand-in for Slithen. If Slithen's licence allows web use,
add `slithen.woff2` to this folder and un-comment the `@font-face` block in `index.html`.
