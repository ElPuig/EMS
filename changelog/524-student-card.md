# What's new

## Student card PDF (replaces the one Esfera generates):

- New "Print student card" on the students list (selection), on a student's form and, as "Print student cards", on a group's form (every student whose main group it is). Each card is CR80-sized (85.6 x 54 mm, fits the usual card holders), ten per A4 sheet in two columns, cut by hand.
- Every card shows the centre (logo, name, address, phone), the academic year in force, the student's photo (a silhouette when missing), name, identity document (DNI/NIE, or passport), birth date and IDALU, plus a Code128 barcode of the IDALU for a future check-in at the entrance.
- A big coloured band with the main group's level (ESO, BTX, CFGB, CFGM, CFGS, PFI, EFPS) and its study and course: whether a student may go out at break time depends only on the level, so the teacher at the door reads it from the band and EMS stores no per-student exit permission. Each level has its own colour (new "Student card colour" on the level, preset for the official levels and editable).
- A back side for double-sided printing (each sheet of fronts followed by its sheet of backs, mirrored so every back lands behind its front): the Departament d'Educació i Formació Professional's logo, the centre's details and a "personal and non-transferable" note.
- The centre's stamp is uploaded once in Settings (EMS > Center Data > "Student card stamp") and printed on every card; without it the card leaves an empty box to stamp by hand.
- Printing follows the student's other actions: Academic admin, Secretary and Head of Studies print any student's card, a tutor (and the chiefs above them) only their own students'.
- User manuals in Catalan, Spanish and English: printing the cards (secretary, shared with tutors) and setting up the stamp and level colours (admin), with screenshots.

# Internal changes

## Student card screenshots and a simulated stamp:

- New -standard screenshot test for the student card manuals, and a drawn "MOSTRA" rubber stamp (draw_invented_centre_stamp) in the shared test helpers, so tests, previews and manuals never use a real stamp.
