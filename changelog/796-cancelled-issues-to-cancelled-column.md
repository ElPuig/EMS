# Internal changes

## Cancelled issues move to Cancelled on the board by themselves:

- New workflow `project-status-on-close.yml`: when an issue is closed, it sets its card on the project board according to the close reason (closed as "not planned" or duplicate goes to "Cancelled", any other close to "Merged"), adding the issue to the board if it wasn't there.
- Replaces the board's built-in "Item closed" automation, which sent every closed issue to the same column and had to be undone by hand for cancelled ones; that automation must be disabled once this is in `main`.
- Needs the repository secret `PROJECTS_TOKEN` (organization permission "Projects: Read and write").
