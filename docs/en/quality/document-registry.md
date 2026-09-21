[Català](../../ca/quality/document-registry.md) | [Castellano](../../es/quality/document-registry.md) | [English](document-registry.md)

---

# Processes, procedures and documents

**Quality → Documentation** holds the structure of the quality documentation: the processes, their
procedures and their documents, each with its link to Drive. The documents themselves (their content,
version and approval) are kept in Drive.

**Who has access:** everyone with the Quality menu can consult it. Quality coordination and management
can also change it.

---

## Consulting and editing

Every process, procedure and document opens **read-only**. To change it (quality coordination and
management):

1. Click **Edit** in the header. The fields become editable.
2. Make the changes and save (cloud icon), or discard them (cross icon).

Saving or discarding brings the record back to read-only.

## Processes

**Quality → Documentation → Processes.** Each process has its code (`PE1`, `PC2`, `PS1`...), its name and
its kind (strategic, key or support). Drag the rows to change the order.

Open a process to see, in its tabs:

- **Document** — the process sheet itself, shown inside the screen. **Open document** opens it in Google
  in a new tab, to edit it there.
- **Procedures** and **Documents** — what hangs off the process. With **Edit** you can add or change them
  from there.

To go to one of its procedures or documents, click its row: it opens in its own form, and the breadcrumbs take you back to the process. Every process, procedure and document opens on
its **Document** tab.

The process sheet's link is set with **Edit**, in the **Link** field.

## Procedures

**Quality → Documentation → Procedures**, grouped by process. Each procedure has its code (`PE3.01`), its
name and its process. Open it to see, in its tabs, its own sheet (**Document**, the same way as a process)
and its **Documents**.

## Documents

**Quality → Documentation → Documents**, grouped by process. Click a document to open it: the document
itself is shown inside the screen, and **Open document** opens it in Google in a new tab, to edit it there.

| Field | What to fill in |
|---|---|
| **Code** | The document's code (`PE3.01.15`). Leave it empty if the document has none |
| **Name** | The document's name |
| **Procedure** | The procedure it belongs to. The process fills itself |
| **Process** | Only for documents that hang straight off a process, with no procedure |
| **Link** | The document's address as copied from the browser |
| **Process map** | Only for the document shown in **Quality → Process map** |

The document is shown inside EMS for Google Docs, Sheets, Slides and files in Drive. For any other kind
of link, use **Open document**.

- **Add a document:** **New**, fill in the fields and save.
- **Retire a document that is no longer in force:** select it in the list, **Actions → Archive**. To see
  archived ones, use the **Archived** facet.
- **Find what is missing:** the **No link** and **Not coded yet** facets.

## Loading many links at once

The same file can carry processes, procedures and documents: each line is matched by its code.

1. Prepare a CSV file with two columns, the code and the link (for example exported from a spreadsheet):
   ```
   code,url
   PE3.01.15,https://docs.google.com/document/d/.../edit
   ```
2. **Quality → Documentation → Documents → Load links** (quality coordination and management).
3. Choose the file and click **Load**.
4. The result says how many links were loaded, which codes do not exist and how many processes,
   procedures and documents are still without a link.
