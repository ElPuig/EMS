# What's new

## Erasmus+ calls and student applications (phase 1 of #682):

- New *Erasmus+* menu for the Erasmus team (new group `ems.group_erasmus`, given by the roles "Erasmus coordinator", now linked to it, and the new "Erasmus mobility technician"). The Head of Studies and the Director see the applications too.
- Calls (`ems.erasmus.call`) with dates, the published call PDF, the text for applicants, modalities (`ems.erasmus.call.modality`: project, places, period, and the levels whose students apply in each one, any year) and the documents they ask for (`ems.erasmus.call.document`: required, optional or required for minors, and confidential). Duplicating a call copies its modalities and documents.
- New portal page `/my/erasmus`: the student sees the calls they can apply to, fills in the form, uploads the documents (every version is kept), saves a draft and submits; each submission emails a receipt with the files. The answers can be changed until the closing date. The portal card only appears to students who can apply or have applied; families don't see it.
- Review by the Erasmus team: each document marked valid or needing changes, requirements check, corrections request by email with the call's deadline (the student can then upload only what was asked for), admit (both checks met and every required document valid) or exclude (with a reason). Closing the call marks unsent drafts as not submitted.
- The serious-sanction check is reserved to the Head of Studies or the Director, who can open the applications but change nothing else; confidential documents are only visible to the Erasmus team.
- Manuals: new `erasmus/` role folder (team), an applicant manual for students and the sanction check for the Head of Studies, in Catalan, Spanish and English. Developer doc in `docs/en/developers/erasmus/erasmus.md`.
