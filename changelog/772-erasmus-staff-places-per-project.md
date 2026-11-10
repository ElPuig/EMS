# Breaking changes

## Erasmus+ staff call: places per project instead of modalities:

- A staff call no longer has modalities: staff compete in one list and only see the call's total places. The Erasmus team splits those places among the active projects that pay them in a new "Places per project" table (`ems.erasmus.call.project`, only the team's), whose sum is the call's places (`_ems_places()`, used by the ranking, resolutions, offers and the publishing warning).
- The team assigns the project on each staff mobility (only the call's projects; `_check_project` refuses another). It brings that project's documents (`project_kind` now comes from the project for staff) and the form shows the places left ("2026-VET: 1 of 2 places left") with a warning, not a block, when the project has more mobilities than places.
- Upgrade (`migrations/18.0.0.48.0/post-migrate.py`, to fold into the release version's folder): each staff modality's places go to the project its mobilities already use, or the only active project of its kind; its mobilities without a project get it; when it cannot be resolved, a note on the call asks the team to add the places by hand. The staff modalities are then deleted. On this dev DB the call had two active VET projects, so its 6 VET places were left for the team, with the note.

# What's new

## Erasmus+ projects get a short name:

- `ems.erasmus.project.code` ("Short name", e.g. 2026-VET), taken from the agreement number (year and VET/HED) and editable. It is what lists and dropdowns show; both can be searched.

## Erasmus+ staff call: accepted places without a project are warned (note 7.1):

- The staff call warns "N places accepted without a project" (`places_without_project`), and its Applications and Mobilities, opened from the call, show the project instead of an empty modality column.
