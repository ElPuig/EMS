# Changes:

## Convalidation portal only shows official decisions (issue #719):
- Students and families no longer see the per-subject decisions (convalidated/rejected, grade, remarks) nor the request's comments while the request is still being processed: the Head of Studies can still change a decision and the Director can send the proposal back, so students thought the process had ended or asked why something they had seen granted was later rejected.
- Until the secretariat registers the resolution (request Completed or Rejected), the portal lists only the requested subjects, the state of the request and a note saying the resolution will appear there once registered.
- A subject refused on a request that is still being processed no longer reappears in the new-request form (which also gave the provisional refusal away); it becomes requestable again once the refusal is official.
- One rule (`_ems_resolution_is_official()`) now decides what the portal page, the resolution download and the requestable subjects treat as official. Family and Head of Studies manuals (ca/es/en) and the developer doc updated.
