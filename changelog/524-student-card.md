# What's new

## Student card PDF (replaces the one Esfera generates):

- New "Print student card" on the students list (selection), on a student's form and, as "Print student cards", on a group's form (every student whose main group it is). Each card is CR80-sized (85.6 x 54 mm, fits the usual card holders), ten per A4 sheet in two columns, cut by hand.
- Every card shows the centre (logo, name, address, phone), the academic year in force, the student's photo (scaled to fit without distorting it, a silhouette when missing), name, identity document (DNI/NIE, or passport), birth date and IDALU, plus a Code128 barcode of the IDALU for a future check-in at the entrance.
- A band split in two rounded blocks. On the left, the main group's level (ESO, BTX, CFGB, CFGM, CFGS, PFI, EFPS) in big letters with the study's acronym (SMX, not its full name) and the course year big in a white circle, on the level's own soft colour (new "Student card colour" on the level: a closed pastel palette without red or green, preset for the official levels and editable).
- On the right, whether the student may leave the centre, for the teacher at the door: "Pot sortir del centre" on green when the student is of age or the family accepted the "Leave the Centre" authorization for the academic year in force, "No pot sortir del centre" on red otherwise. Worked out when the card is printed.
- A modern, soft look: pastel colours with dark text, grey labels, rounded photo and blocks.
- A back side for double-sided printing (each sheet of fronts followed by its sheet of backs, mirrored so every back lands behind its front): the Departament d'Educació i Formació Professional's logo, the centre's details and a "personal and non-transferable" note.
- The centre's stamp is uploaded once in Settings (EMS > Center Data > "Student card stamp") and printed on every card; without it the card leaves an empty box to stamp by hand.
- Printing follows the student's other actions: Academic admin, Secretary and Head of Studies print any student's card, a tutor (and the chiefs above them) only their own students'.
- User manuals in Catalan, Spanish and English: printing the cards (secretary, shared with tutors) and setting up the stamp and level colours (admin), with screenshots.

## New "Leave the Centre" authorization type:

- Authorization templates get a new type, "Leave the Centre". The centre creates the form itself (with its legal text) from Academic management; an accepted answer for the academic year in force sets the new "Leave the Centre" indicator on the student (Yes/No badge on the form, column on the students lists), which the student card reads.

# Internal changes

## Student card screenshots and a simulated stamp:

- New -standard screenshot test for the student card manuals, and a drawn "MOSTRA" rubber stamp (draw_invented_centre_stamp) in the shared test helpers, so tests, previews and manuals never use a real stamp.
