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

Built on the Jergusino brand guide v5: Ink ground, Cream text, Yellow only on pointers
(the script lead-in, the @, the button arrow). Loud headline bottom-left at F, one quiet
group top-right.

Fonts, in `assets/`:
- `slithen.woff` and `borisna.woff`: the brand fonts, trimmed to Latin + Slovak characters.
- The *you get the* script is Edwardian Script ITC turned into an SVG outline inside
  `index.html`, so the font file itself is never published.
- `favicon.svg`: the mark (S with the Yellow bar).

Licences: Borisna is a demo font, free for private, non-profit use only. Before you sell
anything through this list, buy the commercial licence from Koplexs Studio.
Slithen shipped with web-font files; confirm your licence covers web use.

## Sending from no-reply@jergusino.com (optional)

Gmail can't send from a custom-domain address by itself, so the script can send
through Brevo's free plan (300 emails a day) instead:

1. Create a free Brevo account, add **jergusino.com** under Senders, Domains & IPs,
   and add the DNS records Brevo shows (DKIM, DMARC, Brevo code) at your domain registrar.
2. Brevo → SMTP & API → API keys → generate a key.
3. Apps Script → Project Settings → Script properties:
   - `BREVO_API_KEY` = the key (never paste it into Code.gs: this repo is public)
   - `SENDER_EMAIL` = `no-reply@jergusino.com`
   - `REPLY_TO` = your real inbox, so "reply unsubscribe" still reaches you
4. Run `testSetup` once, then Deploy → Manage deployments → New version.

Without `BREVO_API_KEY`, or if Brevo fails, emails are sent from the Google account as before.
