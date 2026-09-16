# Fixes

## Accented names and titles now sort correctly across the app (issue #454):
The database's default text sorting treated accented letters (á, é, í, ó, ú, ñ, ç...) as coming
after 'Z' instead of next to their base letter, so a teacher named "Álvaro..." or a student named
"Ángela..." would land at the very end of an alphabetically-sorted list instead of with the other
A's. Fixed at the database level (PostgreSQL ICU collation) for the columns behind the app's main
people and catalog list views: students, families and other contacts, teachers, groups, subjects,
studies and levels. No visual or behavioral change beyond correct alphabetical order - confirmed
against this centre's own real teacher/student records (e.g. "Álvaro Heredero" now sorts right
after "Alexandra..." instead of after "Yolanda...").
