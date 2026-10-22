# What's new

## Each kind of meeting can only be started by whom it belongs to:

Every minute type now says who can start it: some posts (for any scope) and/or the people of its own scope (a department's chiefs and those above them; a group's tutor, those above them and its teachers; a workgroup's members), and anybody when neither is set. A teacher is only offered the types they can start and, for a scoped one, only their own departments, groups or workgroups; the server refuses the rest. Seeded: generic for everybody, department meetings by its chiefs, claustre by the management team (Director, Head and Deputy Head of Studies, Secretary), teaching team by the group's tutor and teachers, improvement teams by the quality coordinator (meetings also by the team's members). Administrators can always start any.

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

## Department, workgroup and group dropdowns offer the user's own first:

In every dropdown of EMS, the departments the user belongs to or heads, the workgroups they are a member of and the groups they tutor or teach come first; for departments, the other departments of the same area (VET, ESO/BTX, ASP) come next; the rest follow (departments sorted by their path). Departments now show in the reader's language everywhere (the stored complete_name mixed Catalan, Spanish and English) and can be found by their translated name, a parent's name offering the departments under it. A shared mixin (ems.mine_first_mixin), which also replaces the approver dropdown's own ems_first_ids code.

## Agreements are reachable from both sides:

The same agreements and actions screen now appears in the staff menu with "mine" and "open" applied by default — answering "what do I owe and by when" — and in the Quality menu for the whole picture. An agreement records the minute it was taken in.

## Minutes are restricted to the scopes each role belongs to:

Record rules replace what was previously unrestricted write access: the staff sees the minutes of its own departments, workgroups, groups and staff meetings, plus any it attended or has to approve, and writes only what is not approved yet. Above that, minutes follow the chain of command, not the post: a department's minutes reach its chiefs, the Head or Deputy Head of Studies it hangs from (the Deputy Head of Studies for VET sees the VET departments, the Head of Studies the ESO/BTX ones) and the Director, and a teaching team's the chain of its group's tutor. The secretariat goes by its own scopes too. Only the quality committee, quality coordination and the administrator see every minute.

## The Quality menu belongs to the quality committee:

The Quality menu is now seen by the quality committee, quality coordination and management, instead of quality coordination, management, the head of studies and the secretariat (who keep minutes and agreements in the Meetings menu). The committee's access is the existing Quality "Manager" group, renamed "Committee member" (its old description, "identical to Manager", no longer held). It can still be given by hand from the user form, and the catalogue's "Quality Comission" workgroup now feeds it: joining the workgroup gives it, leaving takes it away (except to quality coordination or to someone who had it by hand), and every install and upgrade adds the members the workgroup already has.

## A minute and its attendance session convene the same people:

The minute's attendee list and the attendance session's convened list were worked out by two separate sets of rules that did not quite agree. They now share one: a department convenes its members and those of the departments under it (so a meeting of a whole area, such as VET, convenes all of its departments), a workgroup its members, and a group its teachers together with its tutor, even when the tutor has no subject of their own in it. Attendance sessions gain that last option, "A group's teaching team", and a session prepared from a teaching team's minute keeps it, so loading the convened people again on the session finds the same list. Anybody else can still be added by hand in both, and the minute also keeps taking people from outside EMS.

## People from outside EMS in a minute:

A minute can now record people who are not in EMS (a student's family, a teacher from another school, a speaker) with first name, surname, an optional email and their organisation or relationship, and whether they came. They are written by hand whatever the attendance mode, count as attendees, and appear in the minute's PDF by name and organisation; their email is never printed. Each one can be chosen to receive the meeting's call, which then reaches them in a message of their own (the staff's call shows every recipient), without the link to the previous minute they could not open. The list stays hidden behind an "Add people from outside EMS" switch until somebody is added.

## The chain of command of whoever writes a minute can edit it:

A Seminar Chief above the teacher who wrote a minute could not edit it when a Department Chief above both was the approver, because only the approver's chain of command was taken into account. Now the chain above the writer can edit it too, and the same applies to the minute's agreements, their follow-up and its NFC attendance session.

## NFC attendance can be corrected by hand from the minute:

Whoever runs a meeting can now fix its NFC attendance when a tag was left at home or failed: the minute's Actions > Correct the attendance opens the attendance session, where people are marked present (by hand) or justified, reopening it first if it was already closed. The minute's lists update at once, without closing the session again. It is available while the minute is not approved, to whoever may write it (writer, approver and their chain of command), who also find these sessions under Meetings > Attendance. Head of Studies, the secretariat and the administrator keep every session as before.

## Agreements and their follow-up follow the chain of command:

Agreements and improvement actions were seen and edited centre-wide by the secretariat, every Head of Studies, the Director and every Department Chief, and any teacher could read the follow-up of any agreement. Now they go by the same chain of command as minutes, with three ways of being in an agreement: whoever manages its content (the chain of command of its department or group's tutor and, while the minute is not approved, whoever writes or approves it) changes what was agreed; the responsible people, the holders of the responsible post and their chain of command report its progress through follow-up entries (Actions > Add follow-up) and keep its description up to date from the agreement's form (how to carry it out: written in the minute by whoever writes it, and printed in its PDF), without changing what was agreed; and the new "People involved" (e.g. a whole department that has to update its syllabuses) only read it and its follow-up. Responsible and involved people follow the agreement and are notified of every follow-up entry. The quality committee, quality coordination and the administrator manage them all. An agreement opens read-only for whoever may not change it, and its scope is one at a time (marking it centre-wide empties the department, group and workgroup).

## Committee members read every survey but edit only their own:

A committee member used to see and edit every survey of the centre, since the Committee member group had no record rule on the survey models. It now gets the same two rules quality coordination had (read every survey, create/edit/delete only the ones they created); coordination keeps them through its implied group and the administrator keeps full control. Agreed with the author of the survey integration.

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

# Fixes

## A meeting created by mistake can be deleted while in draft:

Minutes had no way to be deleted. Whoever can write a minute now finds Actions → Delete while it is still a draft (it takes its agenda, lines, agreements and draft NFC attendance session with it); from the meeting on, deleting is refused for every role, administrators included.

## The NFC attendance box of a minute was in English:

The three messages of the minute's NFC attendance box (save the minute first, the lists fill in by themselves, attendance is closed) are rendered by Odoo as a single translatable term, which had no Catalan or Spanish translation.

## The call could still be sent once the minute was sent for approval:

Actions → Send the call (and Send the call again) stayed available while the minute was "To approve". It now disappears as soon as the minute is sent for approval, and the server refuses it in that state too.

# Internal changes

## Screenshots in the minutes and agreements manuals:

The teachers' minutes manual (9 screenshots) and the quality manual on agreements (4) are now illustrated, in Catalan with invented data. They are generated by TestDocsScreenshotsMinutes, which builds its own department, people, minutes and agreements inside the rolled-back test transaction.

## Shared machinery for anything signed and filed:

`ems.signed.record` holds what minutes, audit reports and the management review all need — code, date, state, controlled template and version, generated PDF — so the institutional header and the versioning policy live in one place.

## The minute model moved and grew:

`models/documentation/` and `views/documentation/` are gone: the minute belongs to the quality area now. The old free-text type field is kept in step with the new type catalogue rather than dropped, because dropping it would leave a not-null column behind and break every insert; it can be removed by a version that ships a migration.

A minute is set by one start date and time, from which its date, the time it prints and its course follow.

## Filing the PDF in Drive is deliberately not done yet:

It needs a Drive scope on the service account and the account made a content manager of the shared drives, which is a Google Workspace administration change. The upload sits behind a single method that logs the gap rather than failing silently, and the PDF is available as an attachment meanwhile.

# Related with

- Closes #497
