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
const SITE_ROOT = "https://jergusino.github.io/"; // the main site
const FROM_NAME = "Jergušino";
const LINK_HOURS = 48;
const TOOL_URL = "https://jergusino.com/font-tool/tool/"; // the Font Tool, sent to everyone who signs up on jergusino.com/font-tool/

// ---------- Web endpoints ----------

function doPost(e) {
  const p = (e && e.parameter) || {};
  const email = String(p.email || "").trim().toLowerCase();
  if (!/^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,24}$/.test(email)) return json("invalid");

  // The Font Tool page: always email the link to the tool, whether or not the address is already in the sheet.
  if (p.list === "font-tool") return sendTool(email, p);

  // Don't send the same person more than one confirmation email every 10 minutes.
  const cache = CacheService.getScriptCache();
  if (cache.get("sent:" + email)) return json("pending"); // email already sent in the last 10 minutes

  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const book = SpreadsheetApp.openById(SHEET_ID);
    if (listHas(mainSheet(book), email, "newsletter")) return json("already"); // already confirmed: no new email

    const pending = pendingSheet(book);
    const token = Utilities.getUuid().replace(/-/g, "");
    addRow(pending, { "Signed up": new Date(), "Email": email, "Token": token, "Source": String(p.source || "").slice(0, 100), "Consent": String(p.consent || "").slice(0, 200) });
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
    const rows = readRows(pending);
    const i = rows.findIndex(r => r["Token"] === token);
    if (i === -1) return page("ups", "Neplatný odkaz", "Tento odkaz už bol použitý alebo nefunguje. Ak je tvoj e-mail už potvrdený, si v zozname. Ak nie, prihlás sa znova na stránke.");

    const created = rows[i]["Signed up"], email = rows[i]["Email"], source = rows[i]["Source"], consent = rows[i]["Consent"];
    if (Date.now() - new Date(created).getTime() > LINK_HOURS * 3600 * 1000) {
      pending.deleteRow(rows[i]._row);
      return page("ups", "Odkaz vypršal", "Odkazy platia " + LINK_HOURS + " hodín. Prihlás sa znova na stránke a príde ti nový.");
    }

    const main = mainSheet(book);
    if (!listHas(main, email, "newsletter")) addRow(main, { "Confirmed": new Date(), "Email": email, "Source": source, "Consent": consent, "Signed up": created, "List": "newsletter" });
    // Remove every pending row for this email (they may have signed up twice).
    for (let r = rows.length - 1; r >= 0; r--) if (rows[r]["Email"] === email) pending.deleteRow(rows[r]._row);
    return page("hotovo", "Si v zozname", "Ďakujem za potvrdenie. Prvé súbory ti pošlem na " + email + ".");
  } finally {
    lock.releaseLock();
  }
}

// ---------- Font Tool ----------

// Sends the link to the Font Tool every time someone asks for it, even if the same
// address asked before. The address is written once into the Subscribers tab with
// List = "font-tool" (asking again does not add a second row).
function sendTool(email, p) {
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const main = mainSheet(SpreadsheetApp.openById(SHEET_ID));
    if (!listHas(main, email, "font-tool")) {
      addRow(main, { "Signed up": new Date(), "Email": email, "Source": String(p.source || "").slice(0, 100), "Consent": String(p.consent || "").slice(0, 200), "List": "font-tool" });
    }
  } finally {
    lock.releaseLock();
  }
  const text =
    "Ahoj,\n\ntu je tvoj Font Tool: " + TOOL_URL + "\n\n" +
    "Nahraj doň font (.ttf alebo .otf) a tool doň dorobí chýbajúce slovenské písmená. Font sa spracuje priamo v tvojom prehliadači.\n\nJergušino";
  const html =
    '<div style="background:#060909;padding:32px 24px;font-family:Georgia,serif;color:#FAF1D6">' +
    '<img src="' + SITE_URL + 'assets/img/wordmark.svg" alt="Jergušino" width="150" style="display:block;width:150px;height:auto;border:0">' +
    '<h1 style="margin:32px 0 12px;font-size:30px;line-height:1;text-transform:uppercase;font-family:Impact,\'Arial Narrow\',sans-serif;font-weight:400;color:#FAF1D6">Tvoj Font Tool</h1>' +
    '<p style="margin:0 0 24px;font-size:17px;line-height:1.5;color:#FAF1D6">Nahraj doň font (.ttf alebo .otf) a tool doň dorobí chýbajúce slovenské písmená z jeho vlastných častí. Font sa spracuje priamo v tvojom prehliadači.</p>' +
    '<p style="margin:0 0 24px"><a href="' + TOOL_URL + '" style="display:inline-block;border:2px solid #FAF1D6;padding:14px 22px;color:#FAF1D6;text-decoration:none;font-size:17px">otvoriť Font Tool <span style="color:#FFC600">&rarr;</span></a></p>' +
    '<p style="margin:0;font-size:14px;line-height:1.5;color:#FAF1D6">Odkaz si ulož, funguje stále.</p>' +
    '</div>';
  sendMail(email, "Tvoj Font Tool od Jergušina", text, html);
  return json("sent");
}

// ---------- Helpers ----------

// Everyone lives in one tab, "Subscribers" (found by name, so other tabs, like a
// linked Google Form, can't get in the way). The List column says what they signed
// up for: "newsletter" (confirmed by email) or "font-tool" (got the Font Tool link). The first time, the
// original "Untitled" tab is renamed to "Subscribers" so existing signups stay.
const MAIN_TAB = "Subscribers";
const MAIN_HEADER = ["Confirmed", "Email", "Source", "Consent", "Signed up", "List"];

function mainSheet(book) {
  let s = book.getSheetByName(MAIN_TAB);
  if (!s) {
    s = book.getSheetByName("Untitled");
    if (s) s.setName(MAIN_TAB);
    else s = book.insertSheet(MAIN_TAB, 0);
  }
  if (s.getLastRow() === 0) s.appendRow(MAIN_HEADER);
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

// Rows are read and written by column name (the header in row 1), so the columns
// can be moved or new ones added in the sheet without breaking anything.
function headers(sheet) {
  const n = sheet.getLastColumn();
  return n ? sheet.getRange(1, 1, 1, n).getValues()[0].map(h => String(h).trim()) : [];
}

function addRow(sheet, values) {
  const h = headers(sheet);
  Object.keys(values).forEach(k => {
    if (h.indexOf(k) === -1) { h.push(k); sheet.getRange(1, h.length).setValue(k); }
  });
  sheet.appendRow(h.map(k => (k in values ? values[k] : "")));
}

function readRows(sheet) {
  const h = headers(sheet), n = sheet.getLastRow();
  if (n < 2 || !h.length) return [];
  return sheet.getRange(2, 1, n - 1, h.length).getValues().map((r, i) => {
    const o = { _row: i + 2 };
    h.forEach((k, c) => (o[k] = r[c]));
    return o;
  });
}

// Is this address already in the Subscribers tab for this list? Rows without a List
// value are newsletter subscribers from before the column existed.
function listHas(sheet, email, list) {
  return readRows(sheet).some(r =>
    String(r["Email"]).trim().toLowerCase() === email && (String(r["List"] || "newsletter").trim() || "newsletter") === list);
}

function sendConfirmation(email, token) {
  const link = ScriptApp.getService().getUrl() + "?confirm=" + token; // this deployment's own /exec link
  const text =
    "Ahoj,\n\nniekto (dúfam, že ty) chce na túto adresu dostávať súbory zadarmo od Jergušina.\n\n" +
    "Potvrď to tu: " + link + "\n\n" +
    "Odkaz platí " + LINK_HOURS + " hodín. Ak to nie si ty, tento e-mail ignoruj a nič sa nestane.\n\nJergušino";
  const html =
    '<div style="background:#060909;padding:32px 24px;font-family:Georgia,serif;color:#FAF1D6">' +
    '<img src="' + SITE_URL + 'assets/img/wordmark.svg" alt="Jergušino" width="150" style="display:block;width:150px;height:auto;border:0">' +
    '<h1 style="margin:32px 0 12px;font-size:30px;line-height:1;text-transform:uppercase;font-family:Impact,\'Arial Narrow\',sans-serif;font-weight:400;color:#FAF1D6">Potvrď svoj e-mail</h1>' +
    '<p style="margin:0 0 24px;font-size:17px;line-height:1.5;color:#FAF1D6">Niekto (dúfam, že ty) chce na túto adresu dostávať súbory zadarmo odo mňa. Potvrď to kliknutím nižšie.</p>' +
    '<p style="margin:0 0 24px"><a href="' + link + '" style="display:inline-block;border:2px solid #FAF1D6;padding:14px 22px;color:#FAF1D6;text-decoration:none;font-size:17px">áno, pošli mi súbory <span style="color:#FFC600">&rarr;</span></a></p>' +
    '<p style="margin:0;font-size:14px;line-height:1.5;color:#FAF1D6">Odkaz platí ' + LINK_HOURS + ' hodín. Ak to nie si ty, tento e-mail ignoruj a nič sa nestane.</p>' +
    '</div>';
  sendMail(email, "Potvrď e-mail a získaj súbory zadarmo", text, html);
}

/**
 * Sends one email.
 * - If a Brevo API key is saved (Project Settings → Script properties → BREVO_API_KEY),
 *   it sends from SENDER_EMAIL (e.g. no-reply@jergusino.com) through Brevo.
 * - Otherwise, or if Brevo fails, it falls back to sending from this Google account.
 * Replies go to REPLY_TO, if set, so "reply unsubscribe" still reaches you.
 * Keys live in Script properties, never in this file, because this file is public on GitHub.
 */
function sendMail(to, subject, text, html) {
  const props = PropertiesService.getScriptProperties();
  const key = props.getProperty("BREVO_API_KEY");
  const sender = props.getProperty("SENDER_EMAIL") || "no-reply@jergusino.com";
  const replyTo = props.getProperty("REPLY_TO");

  if (key) {
    const payload = { sender: { name: FROM_NAME, email: sender }, to: [{ email: to }], subject: subject, htmlContent: html, textContent: text };
    if (replyTo) payload.replyTo = { email: replyTo };
    const res = UrlFetchApp.fetch("https://api.brevo.com/v3/smtp/email", {
      method: "post",
      contentType: "application/json",
      headers: { "api-key": key, accept: "application/json" },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true,
    });
    if (res.getResponseCode() < 300) return "brevo";
    console.error("Brevo refused the email (" + res.getResponseCode() + "): " + res.getContentText() + " — sending from Gmail instead.");
  }

  const opts = { to: to, subject: subject, body: text, htmlBody: html, name: FROM_NAME };
  if (replyTo) opts.replyTo = replyTo;
  MailApp.sendEmail(opts);
  return "gmail";
}

function json(status) {
  return ContentService.createTextOutput(JSON.stringify({ status: status })).setMimeType(ContentService.MimeType.JSON);
}

// The confirmation pages look like the newsletter page: the site's own stylesheet,
// logo in the header, the same footer.
function page(lead, title, message) {
  const esc = t => String(t).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const desc = /[gjpqyf]/.test(lead) ? " desc" : "";
  const arrow = '<svg class="arr" viewBox="0 0 24 12" width="24" height="12" aria-hidden="true"><path d="M0 5h18V0l6 6-6 6V7H0z"/></svg>';
  const html =
    '<!doctype html><html lang="sk"><head><meta charset="utf-8">' +
    '<link rel="stylesheet" href="' + SITE_URL + 'assets/css/main.css">' +
    '<link rel="stylesheet" href="' + SITE_URL + 'assets/css/newsletter.css">' +
    '</head><body class="project newsletter">' +
    '<header class="top"><a class="top-mark" href="' + SITE_ROOT + '" target="_top" aria-label="Jergušino, domov">' +
    '<img src="' + SITE_URL + 'assets/img/wordmark.svg" alt="" width="1020" height="262"></a>' +
    '<nav class="top-nav" aria-label="Hlavná navigácia"><a href="' + SITE_ROOT + 'projects/" target="_top">projekty ' + arrow + '</a>' +
    '<a href="' + SITE_URL + '#kontakt" target="_top">kontakt</a></nav></header>' +
    '<main><section class="hero hero--page hero--project"><div class="lockup">' +
    '<p class="lead' + desc + '">' + esc(lead) + '</p><h1 class="title">' + esc(title) + '</h1></div></section>' +
    '<article class="prose"><p class="big">' + esc(message) + '</p>' +
    '<ul class="links"><li><a href="' + SITE_URL + '" target="_top">späť na newsletter ' + arrow + '</a></li></ul></article></main>' +
    '<footer class="foot"><p class="handle"><a href="mailto:jergusino@proton.me" target="_top">jergusino<span class="at">@</span>proton.me</a></p></footer>' +
    '</body></html>';
  return HtmlService.createHtmlOutput(html).setTitle(title + " · Jergušino").addMetaTag("viewport", "width=device-width, initial-scale=1");
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
  const props = PropertiesService.getScriptProperties();
  const usingBrevo = !!props.getProperty("BREVO_API_KEY");
  console.log("4. Sending through: " + (usingBrevo ? "Brevo, from " + (props.getProperty("SENDER_EMAIL") || "no-reply@jergusino.com") : "this Gmail account (no BREVO_API_KEY saved)") +
    " | replies go to: " + (props.getProperty("REPLY_TO") || "the sender"));
  const link = ScriptApp.getService().getUrl() || "(not deployed yet)";
  const how = sendMail(me, "Test: confirmation email setup", "This is a test from your signup script. Link base: " + link,
    '<p style="font-family:Georgia,serif">This is a test from your signup script.</p>');
  console.log("5. Sent a test email to " + me + " via " + how + ". If it says gmail but you expected Brevo, read the red error line above.");
}
