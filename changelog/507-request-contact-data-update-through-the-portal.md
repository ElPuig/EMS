# What's new

## Contact data update requests through the portal:

- Tutors (for their own groups), the secretariat and the Head of Studies can ask students and families to review and complete their contact details: by hand, or for whole groups, studies or levels, from the new menu Educational Community > Students > Student Data (the Students entry becomes a section with the Students list and Student Data) or from the cog menu of the students and groups lists and forms (issue #507).
- The send assistant sends only to students with incomplete data by default, shows what is missing and who will be emailed, lists the students with nobody reachable by email (to be called by phone) and grants portal access to recipients who lack it. While it sends, the screen shows a blocking "Processing the requests…" message so a long run does not look frozen.
- Families (or adult students) answer on the new portal page Contact details (/my/dades-contacte), reached from the Update contact details button of the portal Profile tab (and from a banner on the home while a request is pending). Only portal accounts that act for the student can review and send: a minor's own view-only account, or a family looking at an adult child, cannot, and the request is never emailed to them. They can complete the student's address, identity document, TIS and NUSS, edit their family contacts, add a new one or mark one as no longer a contact. Mandatory: address and DNI/NIE or passport for every student, a personal email for adults (their portal login), and for minors at least one legal tutor with first name, last name and mobile, at least one of them with an email, each with their own. The student's mobile and the family's DNI are optional. An address of the centre's own domain is refused on the form, before it is sent.
- The answer is staged as a diff and only applied when a reviewer (the group's tutor or the chiefs above them, the secretariat, the Head of Studies) approves it, one by one or in bulk; it can also be returned to the family with a reason, which emails them. Reminders are sent in bulk from the follow-up list.

# Changes

## Family contacts recognised by mobile number, not only by document:

- The Esfera import, the "Add family contact" wizard and the new requests share one lookup (res.partner._ems_find_family): by DNI/NIE or passport first, otherwise by mobile/phone number, accepted only when a single family contact holds it and the first name matches. A tutor without a document is no longer duplicated on every import. A number shared under a different name (parents sharing a phone) creates a new contact and is reported as a possible duplicate.
- The "Add family contact" wizard now links a contact already on file (same document, or same mobile and first name) instead of creating a duplicate.

## Portal Profile tab no longer offers the secretariat mailto button:

- The Request a data change button, which opened an email to the secretariat, is removed: contact details are corrected with the Update contact details button, and the name and birth date keep going through the secretariat. The secretariat email setting is no longer used by the portal.

# Internal changes

## Student picking shared by the send assistants:

- The selection of students by hand or by groups, studies and levels (and a tutor's own-students-only limit) moved from the authorization send wizard into a shared mixin, ems.student.scope.mixin, used by both send assistants. A chief above a tutor can now also pick that tutor's groups in the authorization assistant (tutor_scope_user_ids, issue #483), consistent with what they could already send to.
- "Sees every student" (admin, secretariat, Head of Studies) moved to EmsBase.get_user_sees_every_student().

# Related with

- Closes #507
