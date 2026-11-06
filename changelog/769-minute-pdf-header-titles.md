# Fixes

## Minute PDF header titles readable again:
- The title cells of the minute's main table (Date, Nature, Scope, Time, Modality, Place) printed as solid brand colour under text of the same colour, so they could not be read: the PDF renderer ignored the CSS gradient meant to fade the background. They now look like the header row of the minute's other tables (agreements, signatures): brand colour with white uppercase text.

# What's new

## ISO 9001 document reference in the minute PDF footer:
- Every page of a minute's PDF now shows, under the company footer, the controlled document it is printed on: "PE3.01.22 Model d'acta i de registre d'evidències (EMS) – Revisió: 02/11/2026", as ISO 9001 requires. It replaces the reference to the older model (PE3.01.17) that was printed at the end of the minute. Reports can add a line of their own to the footer the same way, whatever layout the company uses.

## Every minute's PDF kept in a Drive folder:
- New setting, Settings > EMS Management > Google Workspace Settings > Minutes folder in Drive (a shared drive folder link). Once set, EMS keeps one file per minute there, named after its code, in whatever state the minute is: it is uploaded when the minute is created and replaced on every change of state (approved minutes file the PDF of their approval), in the background through queue_job. Deleting a minute sends its file to the Drive bin. The minute's form links to its copy (In Drive).
- Uses the Google Workspace service account with the Drive scope; it must be added to the shared drive as Content manager. Dry-run mode only logs. Production: fill in the folder link (https://drive.google.com/drive/folders/18CzLabbkkD6vkAOkhDAuu1jZiFCNC-0z) and add the service account to the shared drive.
