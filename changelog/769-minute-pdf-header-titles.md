# Fixes

## Minute PDF header titles readable again:
- The title cells of the minute's main table (Date, Nature, Scope, Time, Modality, Place) printed as solid brand colour under text of the same colour, so they could not be read: the PDF renderer ignored the CSS gradient meant to fade the background. The faded colour is now computed on the server and applied as a plain background.
