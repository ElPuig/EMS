# Changes

## Auto check-out fallback notice goes to the teacher only (issue #734):

- When the automatic check-out can't use the schedule (the teacher checked in after the last hour their schedule expected that day) and closes the attendance one hour after check-in, the notice now goes only to the teacher, no longer to the Head or Deputy Head of Studies, the area's attendance manager or the administrators (issue #648 had already left out the Department/Seminar Chief). Those approvers only get involved if the teacher requests a correction.
- The notice is rewritten for the teacher: it says, in their own time, when they checked in, the last hour their schedule expected that day and the check-out it set, and tells them to open the attendance and click "Request Correction". It now has Catalan and Spanish translations (it used to arrive in English).
- Teacher manual (ca/es/en): short note explaining this message. Developer docs updated.
