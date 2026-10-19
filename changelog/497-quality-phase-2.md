# What's new

## Minutes and evidence records:

Meeting minutes move into EMS, under the **Meetings** menu (shared with the meeting attendance sessions), the first screen of this work the whole staff sees. One model covers both meeting minutes and evidence records, with the sections each type carries declared as configuration: adding a type of minute no longer needs development.

Seven types ship ready to use — generic, department, staff meeting, teaching team, and improvement team in its three variants — laid out from a catalogue of fifteen sections.

## The work the staff stops doing by hand:

**Attendees arrive preloaded** from the scope of the minute: the department's members, the workgroup's, the teachers of a group, or the whole teaching staff for a staff meeting. **The still-open agreements of the previous minute of the same scope are carried over**, along with any pending topic left unticked, so following up on what was agreed no longer depends on somebody copying it across. **Codes are issued automatically**, per scope and course, so a gap in a department's numbering is visible instead of invisible.

## Setting a minute up in the order a meeting is set up:

The form asks first for the type, then for whose meeting it is (the department, the workgroup or the group, depending on the type; a generic minute lets you choose), then for the date and time, the room and the modality. The title is the minute's own code, which builds up at the top as those fields are filled in and is issued on saving. The date and time are one field with a picker, proposed at the next full hour, and the course follows from the date instead of being asked for.

## Attendance by hand or with the NFC tag, chosen in the minute:

Whoever writes the minute decides how attendance is taken. By hand, the preloaded list is edited as before. With the NFC tag, the minute prepares its own attendance session: the writer opens the kiosk from the minute, people pass their tag, and closing attendance fills the attendee and absentee lists by themselves, justified absences included.

## The agenda is put together, not typed, and sent with the call:

Only the meeting's own items are written, in the tab now called "Items to discuss". The agenda follows from the minute: approving the previous minute when there is one, following up the agreements when some are still open, those items, and any other business. From the draft, "Send the call" emails it to everybody convened together with the date, time and place and a link to the previous minute; it can be sent again whenever something changes, and the second call says it replaces the first. The minute's actions now live in the form's "Actions" dropdown.

## The meeting has a stage of its own, and its minute is written from top to bottom:

Between preparing a meeting and sending its minute for approval there is now the meeting itself. Starting it turns the form into the blocks of the agenda, one under another: attendance, the approval of the previous minute, the open agreements, each item to discuss with a rich-text box of its own, any other business, the new agreements and the pending topics. Each open agreement is reviewed in place (what was said, a new deadline, whether it is done) and that goes into the agreement's own follow-up, so a closed one is not carried to the next meeting. The development of the session is no longer typed as one block: it is put together from what was written on each item.

## A minute that saves itself, and a PDF to read before approving:

While it is being written the minute saves by itself in the writer's pauses, so an hour of meeting no longer hangs on one click. Its PDF can be opened at any moment before approval, marked as a draft. The PDF itself follows the meeting (agenda, approval of the previous minute, follow-up of the agreements, what was said on each item, agreements, pending topics), in a smaller type and with tables kept tight and inside the page whatever was pasted into the texts.

## The minute is approved by a person, and written in the centre's language:

Who approves a minute is now a person rather than a post: whoever answers for the scope that meets comes proposed (a department's chief, a group's tutor, the director), those people come first in the dropdown, and anybody else can be chosen. The same person signs the call. A minute's PDF and its call are always written in the centre's language, whatever language the person producing them works in.

## One controlled template instead of five:

The per-variant minute templates are replaced by a single controlled document with optional sections. The five it replaces are archived in the document structure, and still resolve for any older minute quoting their code.

## Approval and PDF:

A minute goes draft → to approve → approved. Approving records who approved it and when, and renders the PDF, which is kept as an attachment on the record. An approved minute cannot be edited or sent back to draft: a correction is a new version, not an edit.

The PDF quotes the controlled template's code in its footer, and prints the members' identification number only for the minute types that need it.

# Changes

## Agreements are reachable from both sides:

The same agreements and actions screen now appears in the staff menu with "mine" and "open" applied by default — answering "what do I owe and by when" — and in the Quality menu for the whole picture. An agreement records the minute it was taken in.

## Minutes are restricted to the scopes each role belongs to:

Record rules replace what was previously unrestricted write access: the staff sees the minutes of its own departments, workgroups, groups and staff meetings, plus any it attended or has to approve, and writes only what is not approved yet. Above that, minutes follow the chain of command, not the post: a department's minutes reach its chiefs, the Head or Deputy Head of Studies it hangs from (the Deputy Head of Studies for VET sees the VET departments, the Head of Studies the ESO/BTX ones) and the Director, and a teaching team's the chain of its group's tutor. The secretariat goes by its own scopes too. Only the quality committee, quality coordination and the administrator see every minute.

## The Quality menu belongs to the quality committee:

The Quality menu is now seen by the quality committee, quality coordination and management, instead of quality coordination, management, the head of studies and the secretariat (who keep minutes and agreements in the Meetings menu). The committee's access is the existing Quality "Manager" group, renamed "Committee member" (its old description, "identical to Manager", no longer held). It can still be given by hand from the user form, and the catalogue's "Quality Comission" workgroup now feeds it: joining the workgroup gives it, leaving takes it away (except to quality coordination or to someone who had it by hand), and every install and upgrade adds the members the workgroup already has.

## Only whoever gives the approval approves a minute, and every change of state asks first:

The Approve action used to be offered to anybody who could edit the minute, its writer included, and the approver was then overwritten by whoever clicked. Now only the person named to approve it, anybody above them in the chain of command (who stands in when they are away, and can edit the minute to do so), or, with nobody named, a holder of the approver post, and the administrator can approve: the button is hidden from everybody else and the server refuses it before anything is written. Every change of state (start the meeting, send for approval, approve, go back) asks for confirmation; approving says it cannot be undone. Approving also failed for anybody but an administrator: the minute is approved before its PDF is attached, and an approved minute can no longer be written; the PDF is now attached with elevated rights once the approval has been checked.

## A more readable minute PDF:

The minute's PDF starts right under the letterhead (a paper format of its own with a smaller top margin and side margins half as wide again, instead of the company's, and without the layout's empty address block), with its header as a three-column table (date and time, nature and modality, scope and place) whose title cells carry the company colour faded. The text is justified, section titles are larger and underlined, the titles of the items discussed are larger, both with more room above them, no table is split across two pages, and the signatures are a table with a header row like the agreements. Under each name the signature cell leaves room for a validation stamp, the same one the convalidation resolutions print (now a shared template): "Sent for approval in EMS" under the writer and "Approved in EMS" under the approver, each with who did it, when and the minute's code. Sending for approval now records who did it and when for that purpose.

## A minute opens read-only for whoever may only read it:

An attendee or a department colleague used to get the minute's fields as editable and only found out on saving ("doesn't have 'write' access"). The form now asks whether the user may write that minute (`can_edit`, shared with the quality structure's forms through a new `ems.quality.can.edit` mixin) and opens it read-only when not, with no header action and no attendance kiosk buttons; the autosave skips it. Covered by a backend test and a new tour logged in as an attendee teacher.

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
