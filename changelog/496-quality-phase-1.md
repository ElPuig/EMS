# What's new

## Quality management system: process map, controlled documents and actions:

The centre's ISO 9001 quality management system starts moving inside EMS. This first phase brings in the foundation the rest builds on: the process map, the controlled-document registry and a single model for meeting agreements and improvement actions.

A new **Quality** menu, visible only to quality coordination, management, the head of studies and the secretariat. The staff-facing application arrives with the minutes in the next phase, so nobody sees a half-built app in the meantime.

## The centre's process map, loaded as real data:

The eight processes (strategic, key and support), their 48 procedures and 64 controlled documents are loaded from `data/custom/`, with every responsibility expressed as a **post** rather than a person, so the map stays correct when somebody changes job in September.

## Controlled document registry:

Every controlled document now has a record with its code, kind, owner post, version, approval and next review dates, state and supersession. The file itself stays in the centre's Drive: this is the card and the link, not a copy.

Filters answer the questions that used to need a spreadsheet: what is in force, what is pending approval, what is due for review this year, what has no code yet, and which documents still carry a code from a superseded process scheme.

## Agreements and improvement actions are one thing:

A meeting agreement and an improvement action have the same shape — owner, deadline, follow-up, closure — so they are one model with a type. That is what makes a single "what do I owe and by when" screen possible instead of one per origin.

Their state is **derived from the latest follow-up entry** and cannot be typed: moving an action forward means recording what happened and when, which is what leaves the reason on file.

Codes are issued by sequence, per scope and course (`ACORD-INF-2026-27-003`), so a department's agreements are consecutive and a missing one shows.

# Internal changes

## Document links are loaded separately, never from a data file:

A document's Drive link changes whenever the file is replaced, which makes it live application state: the repository's own conventions keep such fields out of synced CSV columns, which would revert them on the next upgrade. A small wizard loads them from a `code,url` file kept outside the repository, resolving the Drive file id so links survive the file being moved or renamed.

The registry as a whole is seeded once and then frozen, reusing the mechanism already in place for groups.

## Course short code:

`ems.course` gains a stored computed short code (`2026-27`) written the way the centre writes it everywhere, and it is the single source of that string for the quality code sequences.

## Access rights found missing by the new tours:

The quality, head of studies and management roles had no read access to `ems.course`, which made any course-scoped list fail to render for them. Caught by the phase's own browser tours, which log in as the least-privileged role that should have access rather than as an administrator.

# Related with

- Closes #496
