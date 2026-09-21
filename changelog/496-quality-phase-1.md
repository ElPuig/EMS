# What's new

## Quality management system: process map, controlled documents and actions:

The centre's ISO 9001 quality management system starts moving inside EMS. This first phase brings in the foundation the rest builds on: the embedded process map, the documentary structure with its links to Drive, and a single model for meeting agreements and improvement actions.

A new **Quality** menu, visible only to quality coordination, management, the head of studies and the secretariat. The staff-facing application arrives with the minutes in the next phase, so nobody sees a half-built app in the meantime.

## Process map:

**Quality > Process map**, the first entry of the app, shows the centre's process map document inside EMS, with a button to open it in Google Docs in a new tab. The map is one more document of the structure, marked as the process map, so its link is changed like any other.

## Documentary structure and links:

Under **Quality > Configuration**, the eight processes, their 48 procedures and 64 documents, each document with its Drive link. A document's form shows the document itself inside EMS (Google Docs, Sheets, Slides and Drive files), built from its ordinary link, and opens it for editing in a new tab: one link per document, no "Publish to the web" copy. The list has a *Load links* button to fill many links at once from a `code,url` file. Seeded in Catalan from `data/custom/`, then kept from the interface.

## Read-only until "Edit":

Process, procedure and document forms open read-only, even for users who may change them. An *Edit* button in the header, shown only to them, unlocks the fields; saving or discarding locks them again.

Deliberately nothing else about a document: version, state, approval and review dates stay in the document itself, in Drive, so nothing has to be updated twice. A first version of this phase kept all of that in EMS as well and was reduced for that reason.

## Agreements and improvement actions are one thing:

A meeting agreement and an improvement action have the same shape — owner, deadline, follow-up, closure — so they are one model with a type. That is what makes a single "what do I owe and by when" screen possible instead of one per origin.

Their state is **derived from the latest follow-up entry** and cannot be typed: moving an action forward means recording what happened and when, which is what leaves the reason on file.

Codes are issued by sequence, per scope and course (`ACORD-INF-2026-27-003`), so a department's agreements are consecutive and a missing one shows.

# Internal changes

## Document links are never in a data file:

The links point into the centre's Drive, and this repository is public, so they are not a CSV column: they are filled in from the interface or loaded with the wizard from a file kept outside the repository.

Processes, procedures and documents are seeded once and then frozen, reusing the mechanism already in place for groups, so edits made from the interface survive upgrades.

## Course short code:

`ems.course` gains a stored computed short code (`2026-27`) written the way the centre writes it everywhere, and it is the single source of that string for the quality code sequences.

## Access rights found missing by the new tours:

The quality, head of studies and management roles had no read access to `ems.course`, which made any course-scoped list fail to render for them. Caught by the phase's own browser tours, which log in as the least-privileged role that should have access rather than as an administrator.

# Related with

- Closes #496
