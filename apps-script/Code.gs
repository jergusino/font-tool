/**
 * Receives signups from the Jergusino landing page and appends them to the
 * private "Newsletter signups" Google Sheet. The sheet is opened by ID, so this
 * works whether the script is attached to the sheet or standalone.
 * Open the /exec link in a browser to check the connection (doGet).
 */
const SHEET_ID = "16P0d7loImDomWPG9GpTgpHCfdGbLckaXOaiameCl6PE"; // "Newsletter signups"

function doGet() {
  const sheet = SpreadsheetApp.openById(SHEET_ID).getSheets()[0];
  return reply("ok: connected to '" + sheet.getParent().getName() + "', rows: " + sheet.getLastRow());
}

function doPost(e) {
  const p = (e && e.parameter) || {};
  const email = String(p.email || "").trim().toLowerCase();
  if (!/^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,24}$/.test(email)) return reply("invalid");

  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const sheet = SpreadsheetApp.openById(SHEET_ID).getSheets()[0];
    if (sheet.getLastRow() === 0) sheet.appendRow(["Timestamp", "Email", "Source", "Consent"]);
    const last = sheet.getLastRow();
    if (last > 1) {
      const existing = sheet.getRange(2, 2, last - 1, 1).getValues().flat();
      if (existing.indexOf(email) !== -1) return reply("duplicate");
    }
    sheet.appendRow([new Date(), email, String(p.source || "").slice(0, 100), String(p.consent || "").slice(0, 200)]);
    return reply("ok");
  } finally {
    lock.releaseLock();
  }
}

function reply(status) {
  return ContentService.createTextOutput(JSON.stringify({ status: status }))
    .setMimeType(ContentService.MimeType.JSON);
}
