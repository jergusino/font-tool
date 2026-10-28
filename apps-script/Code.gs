/**
 * Jergusino newsletter signups with email confirmation (double opt-in).
 *
 * 1. The landing page POSTs an email here.
 * 2. The email is saved in the "Pending" tab and a confirmation email is sent.
 * 3. When the person clicks the link in that email, they are moved to the main
 *    list (first tab). Only confirmed emails ever reach the main list.
 *
 * Links older than 48 hours stop working. Opening the /exec link with no
 * parameters shows a connection check.
 */
const SHEET_ID = "16P0d7loImDomWPG9GpTgpHCfdGbLckaXOaiameCl6PE"; // "Newsletter signups"
const SITE_URL = "https://jergusino.github.io/newsletter/";
const FROM_NAME = "Jergusino";
const LINK_HOURS = 48;

// ---------- Web endpoints ----------

function doPost(e) {
  const p = (e && e.parameter) || {};
  const email = String(p.email || "").trim().toLowerCase();
  if (!/^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,24}$/.test(email)) return json("invalid");

  // Don't send the same person more than one confirmation email every 10 minutes.
  const cache = CacheService.getScriptCache();
  if (cache.get("sent:" + email)) return json("pending"); // email already sent in the last 10 minutes

  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const book = SpreadsheetApp.openById(SHEET_ID);
    if (listHas(mainSheet(book), email)) return json("already"); // already confirmed: no new email

    const pending = pendingSheet(book);
    const token = Utilities.getUuid().replace(/-/g, "");
    pending.appendRow([new Date(), email, token, String(p.source || "").slice(0, 100), String(p.consent || "").slice(0, 200)]);
    sendConfirmation(email, token);
    cache.put("sent:" + email, "1", 600);
    return json("pending");
  } finally {
    lock.releaseLock();
  }
}

function doGet(e) {
  const token = String((e && e.parameter && e.parameter.confirm) || "").replace(/[^a-f0-9]/gi, "");
  if (!token) {
    const book = SpreadsheetApp.openById(SHEET_ID);
    return json("ok: connected to '" + book.getName() + "', confirmed: " + Math.max(0, mainSheet(book).getLastRow() - 1));
  }

  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const book = SpreadsheetApp.openById(SHEET_ID);
    const pending = pendingSheet(book);
    const rows = pending.getLastRow() > 1 ? pending.getRange(2, 1, pending.getLastRow() - 1, 5).getValues() : [];
    const i = rows.findIndex(r => r[2] === token);
    if (i === -1) return page("This link has already been used or doesn’t work.", "If you already confirmed, you’re on the list. If not, sign up again on the page.");

    const [created, email, , source, consent] = rows[i];
    if (Date.now() - new Date(created).getTime() > LINK_HOURS * 3600 * 1000) {
      pending.deleteRow(i + 2);
      return page("This link has expired.", "Links work for " + LINK_HOURS + " hours. Sign up again on the page and you’ll get a new one.");
    }

    const main = mainSheet(book);
    if (!listHas(main, email)) main.appendRow([new Date(), email, source, consent, created]);
    // Remove every pending row for this email (they may have signed up twice).
    for (let r = rows.length - 1; r >= 0; r--) if (rows[r][1] === email) pending.deleteRow(r + 2);
    return page("You’re on the list.", "Thanks for confirming. The first files are on their way to " + email + ".");
  } finally {
    lock.releaseLock();
  }
}

// ---------- Helpers ----------

function mainSheet(book) {
  const s = book.getSheets()[0];
  if (s.getLastRow() === 0) s.appendRow(["Confirmed", "Email", "Source", "Consent", "Signed up"]);
  else if (s.getRange(1, 5).getValue() === "") s.getRange(1, 1, 1, 5).setValues([["Confirmed", "Email", "Source", "Consent", "Signed up"]]);
  return s;
}

function pendingSheet(book) {
  let s = book.getSheetByName("Pending");
  if (!s) {
    s = book.insertSheet("Pending");
    s.appendRow(["Signed up", "Email", "Token", "Source", "Consent"]);
  }
  return s;
}

function listHas(sheet, email) {
  const n = sheet.getLastRow();
  if (n < 2) return false;
  return sheet.getRange(2, 2, n - 1, 1).getValues().flat().indexOf(email) !== -1;
}

function sendConfirmation(email, token) {
  const link = ScriptApp.getService().getUrl() + "?confirm=" + token; // this deployment's own /exec link
  const text =
    "Hi,\n\nSomeone (hopefully you) asked to get free design files from Jergusino at this address.\n\n" +
    "Confirm here: " + link + "\n\n" +
    "The link works for " + LINK_HOURS + " hours. If this wasn’t you, ignore this email and nothing happens.\n\n— Jergusino";
  const html =
    '<div style="background:#060909;padding:32px 24px;font-family:Georgia,serif;color:#FAF1D6">' +
    '<p style="margin:0 0 8px;font-size:15px">@jergusino</p>' +
    '<h1 style="margin:24px 0 12px;font-size:28px;line-height:1.1;text-transform:uppercase;font-family:Impact,\'Arial Narrow\',sans-serif;font-weight:400;color:#FAF1D6">Confirm your email</h1>' +
    '<p style="margin:0 0 24px;font-size:17px;line-height:1.5;color:#FAF1D6">Someone (hopefully you) asked to get free design files from me at this address. Click below to confirm.</p>' +
    '<p style="margin:0 0 24px"><a href="' + link + '" style="display:inline-block;border:2px solid #FAF1D6;padding:14px 22px;color:#FAF1D6;text-decoration:none;font-size:17px">Yes, send me the files <span style="color:#FFC600">&rarr;</span></a></p>' +
    '<p style="margin:0;font-size:14px;line-height:1.5;color:#FAF1D6">The link works for ' + LINK_HOURS + ' hours. If this wasn’t you, ignore this email and nothing happens.</p>' +
    '</div>';
  MailApp.sendEmail({ to: email, subject: "Confirm your email to get the free files", body: text, htmlBody: html, name: FROM_NAME });
}

function json(status) {
  return ContentService.createTextOutput(JSON.stringify({ status: status })).setMimeType(ContentService.MimeType.JSON);
}

function page(title, message) {
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const html =
    '<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>' +
    '@font-face{font-family:Slithen;src:url(' + SITE_URL + 'assets/slithen.woff) format("woff")}' +
    '@font-face{font-family:Borisna;src:url(' + SITE_URL + 'assets/borisna.woff) format("woff")}' +
    'html,body{margin:0;background:#060909;color:#FAF1D6;font-family:Borisna,Georgia,serif;font-size:19px;line-height:1.45}' +
    '.w{min-height:100vh;box-sizing:border-box;padding:40px max(20px,6vw);display:flex;flex-direction:column;justify-content:center;max-width:44em}' +
    'h1{font-family:Slithen,Impact,sans-serif;font-weight:400;text-transform:uppercase;line-height:.9;font-size:clamp(44px,8vw,96px);margin:0 0 .3em}' +
    'a{color:#FFC600}a:hover{color:#FAF1D6}' +
    '</style></head><body><div class="w"><h1>' + esc(title) + '</h1><p>' + esc(message) + '</p>' +
    '<p><a href="' + SITE_URL + '" target="_top">Back to the page</a></p></div></body></html>';
  return HtmlService.createHtmlOutput(html).setTitle("Jergusino").addMetaTag("viewport", "width=device-width, initial-scale=1");
}

// ---------- Setup check: select "testSetup" and click Run in the Apps Script editor ----------
// Runs every step a real signup uses and logs what happens (View → Logs / Execution log).
// It also asks for any permission that's still missing. It sends one test email to you.
function testSetup() {
  const me = Session.getEffectiveUser().getEmail();
  console.log("1. Running as: " + me);
  const book = SpreadsheetApp.openById(SHEET_ID);
  console.log("2. Opened sheet: " + book.getName());
  mainSheet(book);
  const pending = pendingSheet(book);
  console.log("3. Pending tab ready, rows: " + pending.getLastRow());
  console.log("4. Emails left today: " + MailApp.getRemainingDailyQuota());
  sendConfirmation(me, "test-only-this-link-will-not-work");
  console.log("5. Sent a test confirmation email to " + me + ". All good: signups will work once deployed as a New version.");
}
