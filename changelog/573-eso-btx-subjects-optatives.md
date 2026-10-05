# What's new

## ESO and BTX subjects needed by the 2026-27 timetables:

- 34 ESO subjects added to the centre's catalog and to the ESO study: Lectura, Projectes, Actualitat and Religió (1r-4t), Educació Visual i Plàstica (1r, 2n), Música (1r, 3r), Educació en Valors Cívics i Ètics, and the optatives below. 4 BTX subjects added: Literatura Catalana, Formació i Orientació, Món Clàssic and Biomedicina. Without them about 208 weekly hours of the timetables exported from iEduca could not be imported.
- ESO optatives: every optative class is a group (students from every group of the course, enrolled in group + subject), so the centre can change its own offer every year from the UI. 1r-3r optatives of the centre's own use one generic subject per course (Optativa 1r/2n/3r, code `175_2022_OPTn`, never starting with `OPT` because of the Esfera grade importer); those Esfera lists under their own name keep their subject (Francès, Robòtica, Ofimàtica, and new Emprenedoria and Cultura Clàssica for 3r). In 4t every optative is its own curricular subject (new: Emprenedoria, Cultura Clàssica, FOLP, Llatí, Filosofia, Teatre, Expressió Artística, Economia Bàsica); a subject taught in two classes (FiQ, Biologia, FOLP) is one subject with two groups.
- Funcionament de l'Empresa i Disseny de Models de Negoci (iEduca EDN) is not new: it maps to the existing BTX `FEM1`/`FEM2`.

## Academic history keeps the group each subject was taken in:

- Each subject line of the academic history (`ems.student.year_record.subject`) stores, as text, the name of the group it was graded in (`group_name`, from the last round's grade session). For a generic ESO optative subject it is the only record of which optative the student took. Shown in the record's Subjects tab and in the subject line form.

# Fixes

## ESO subject names off by one course:

- `FIQ2`/`FIQ3`/`FIQ4` were named Física i Química (1r)/(2n)/(3r) instead of (2n)/(3r)/(4t), and `ROB3` was named Robòtica (2n) instead of (3r).
