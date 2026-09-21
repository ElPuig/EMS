# What's new

## Minutes and evidence records:

Meeting minutes move into EMS, in a new **Minutes and agreements** menu that is the first screen of this work the whole staff sees. One model covers both meeting minutes and evidence records, with the sections each type carries declared as configuration: adding a type of minute no longer needs development.

Eight types ship ready to use — generic, department for vocational studies and for secondary, staff meeting, teaching team, and improvement team in its three variants — laid out from a catalogue of seventeen sections.

## The work the staff stops doing by hand:

**Attendees arrive preloaded** from the scope of the minute: the department's members, the workgroup's, the teachers of a group, or the whole teaching staff for a staff meeting. **The still-open agreements of the previous minute of the same scope are carried over**, along with any pending topic left unticked, so following up on what was agreed no longer depends on somebody copying it across. **Codes are issued automatically**, per scope and course, so a gap in a department's numbering is visible instead of invisible.

## One controlled template instead of five:

The per-variant minute templates are replaced by a single controlled document with optional sections. The five it replaces are archived in the document structure, and still resolve for any older minute quoting their code.

## Approval and PDF:

A minute goes draft → to approve → approved. Approving records who approved it and when, and renders the PDF, which is kept as an attachment on the record. An approved minute cannot be edited or sent back to draft: a correction is a new version, not an edit.

The PDF quotes the controlled template's code in its footer, and prints the members' identification number only for the minute types that need it.

# Changes

## Agreements are reachable from both sides:

The same agreements and actions screen now appears in the staff menu with "mine" and "open" applied by default — answering "what do I owe and by when" — and in the Quality menu for the whole picture. An agreement records the minute it was taken in.

## Minutes are restricted to the scopes each role belongs to:

Record rules replace what was previously unrestricted write access: the teaching staff sees the minutes of its own departments, workgroups, groups and staff meetings, plus any it attended or has to approve, and writes only what is not approved yet. The secretariat, head of studies, management and quality coordination see them all.

## The seeded quality data is in Catalan, not English:

The process map, the procedures, the controlled-document registry, the minute types and the minute
sections were seeded in English, on the assumption that the Catalan version would be added later as a
translation. It cannot be: those records belong to the centre, not to the module (`__import__.` prefix),
and Odoo's translation exporter only looks at records owned by the module being exported, so a `.po`
entry can never reach them - the value in the CSV is what every reader sees, whatever language they
work in. Phase 1 papered over this with a manual step in the production guide: open 120 records one by
one and translate the name from the interface, on every environment.

All six CSV files now carry the Catalan name directly, taken from the centre's own documents (the
process map, each procedure sheet, the five minute templates), so both environments show the same
wording the quality documentation uses, and the manual translation step is gone from the phase 1 and
phase 2 production guides. Three titles keep the orthographic slips their source documents carry, on
purpose: the registry has to say what an auditor reads in Drive. Module strings - labels, menus,
buttons, the printed minute's headings - are unaffected and keep being translated through the `.po`
files as usual.

# Internal changes

## Shared machinery for anything signed and filed:

`ems.signed.record` holds what minutes, audit reports and the management review all need — code, date, state, controlled template and version, generated PDF — so the institutional header and the versioning policy live in one place.

## The minute model moved and grew:

`models/documentation/` and `views/documentation/` are gone: the minute belongs to the quality area now. The old free-text type field is kept in step with the new type catalogue rather than dropped, because dropping it would leave a not-null column behind and break every insert; it can be removed by a version that ships a migration.

The date of a minute is now a date rather than a timestamp, with the time kept as the minute itself states it, matching how the real templates are written.

## Filing the PDF in Drive is deliberately not done yet:

It needs a Drive scope on the service account and the account made a content manager of the shared drives, which is a Google Workspace administration change. The upload sits behind a single method that logs the gap rather than failing silently, and the PDF is available as an attachment meanwhile.

# Related with

- Closes #497
