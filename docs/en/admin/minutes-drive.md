[Català](../../ca/admin/minutes-drive.md) | [Castellano](../../es/admin/minutes-drive.md) | [English](minutes-drive.md)

---

# Minutes Folder in Drive

EMS can keep a copy of every minute's PDF in a folder of a shared drive, in whatever state the minute is:

- one file per minute, named after its code (for example `ACTA-DEP-2026-27-001.pdf`);
- the file is replaced each time the minute is created or changes state, so only its latest version is kept;
- an approved minute files the PDF of its approval;
- deleting a minute sends its file to the shared drive's bin.

The copy is made in the background, a few moments after the change.

**Required role:** Administrator

---

## Access

Navigate to: **Settings → EMS Management → Google Workspace Settings → Minutes folder in Drive**

---

## Set it up

1. In Google Drive, open the folder of the shared drive where the minutes go and copy its link.
2. Add the service account of the Google Workspace integration (the `client_email` of its JSON key) as a
   member of that shared drive, with the **Content manager** role.
3. In EMS, paste the link in **Minutes folder in Drive** and save.

The Google Workspace integration must be enabled (**Enable Google Workspace**). With **Dry-run
mode** on, nothing is sent to Drive: EMS only writes in its log what it would have filed.

To stop filing minutes in Drive, empty the field. The files already in the folder stay there.

---

[← Back to index](index.md)
