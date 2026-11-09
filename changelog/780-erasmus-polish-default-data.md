# Changes

## Erasmus+ default data in Catalan and Spanish (#780):

- What a new call starts with (modalities, documents with their instructions, checklist, self-assessment questions, commitment letter) and what a new group mobility starts with (selection criteria, documents) is stored in Catalan, Spanish and English, whoever creates it: each student, family or teacher reads it in their own language (notes 2.1 and 9.6 of the 46.0 review). Before, it was stored only in the language of whoever created the call, so a call opened by an English-speaking account showed English texts to everybody. A text changed in the form before saving keeps what was written. Calls and group mobilities created before keep their texts as they were.
- A staff call's modalities are "FP staff" and "Higher education staff", without the project code (it has its own column), and its first step has the same name as the students' one, "Preparation sessions" (note 6.9).
- A checklist step can be "Optional": it is listed (on the portal, with "(optional)") but never holds a mobility back. A new staff call brings "Share it at a department or cycles meeting" as optional, as art. 15 of the call leaves it to each person (note 6.6).

# Internal changes

## Translatable Erasmus+ default texts:

- The default texts' fields are `translate=True`; `models/erasmus/default_data.py` stores each line still holding a default in every installed language after `create()` (and after a `write()` adding lines from the form), matching by name then instructions, with `update_field_translations`. The upgrade only turns the columns into translatable ones, keeping their values.
