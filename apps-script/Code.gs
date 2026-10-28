/**
 * Receives signups from the Jergusino landing page and appends them
 * to the "Newsletter signups" Google Sheet this script is attached to.
 * The sheet itself stays private; this endpoint can only add rows.
 */
function doPost(e) {
  const p = (e && e.parameter) || {};
  const email = String(p.email || "").trim().toLowerCase();

  // Reject anything that isn't an email, and keep fields short.
  if (!/^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,24}$/.test(email)) {
    return reply("invalid");
  }

  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0];
    if (sheet.getLastRow() === 0) {
      sheet.appendRow(["Timestamp", "Email", "Source", "Consent"]);
    }

    // Skip duplicates.
    const last = sheet.getLastRow();
    if (last > 1) {
      const existing = sheet.getRange(2, 2, last - 1, 1).getValues().flat();
      if (existing.indexOf(email) !== -1) return reply("duplicate");
    }

    sheet.appendRow([
      new Date(),
      email,
      String(p.source || "").slice(0, 100),
      String(p.consent || "").slice(0, 200),
    ]);
    return reply("ok");
  } finally {
    lock.releaseLock();
  }
}

function reply(status) {
  return ContentService.createTextOutput(JSON.stringify({ status: status }))
    .setMimeType(ContentService.MimeType.JSON);
}
