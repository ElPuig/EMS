# Changes

## Erasmus+ polish: mobility, group, project, economy and configuration lists:

- Mobilities: the list shows how each record is going ("2 / 11") with short headers, the proposal and the rank optional, and Students / Staff filters; a new cards view shows the mobilities in one column per phase. "Pending validation" has its own list with what was proposed (participant, entity, country, dates, sent on), for the Direction and the Erasmus team.
- A mobility's record table says who handles each document (new non-stored `responsible`) apart from its status, whose "the team uploads it" now reads "Waiting for the team"; it shows the files that count, the team's upload column only on the documents the team hands over, and every version as an optional column.
- Group mobility: the Selection tab starts with the students' table (rank, name, group, average, proposed and final result; the rest optional) and ends with the dates of each step; the Participants tab shows seven columns and nothing red on a withdrawal.
- Projects: no "Active" switch in the list (archived from Actions); the two mobility tables have a title and hide when empty; the exports log shows date, who, what was exported with the participant's or group's name (new non-stored `subject`), confidential and files.
- Economy: the comparison by call opens with three measures (grant, committed, available); the expense lists show one amount, the one that counts; the group mobility column of grant payments and the invoice description are optional. The economic panel calls the project's kind "Kind", as the project list does.
- Quality: the satisfaction surveys' pivot view is removed (the quality panel already breaks the satisfaction down).
- Configuration: host entities have their own list (name, country, city, OID and how many mobilities each one hosted, new non-stored `erasmus_mobility_count`) without the students' group side panel; the organisational support rates open grouped by year, newest first, and a year is never added up in a group's row (`call_year` with `aggregator=None`).
