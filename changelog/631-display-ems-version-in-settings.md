# What's new

## Installed and latest EMS version shown in the settings:
- The EMS Management settings tab ends with an "About" block showing the EMS version running on the installation (the version the database was last upgraded to, not the code on disk), so admins can check it before reporting a problem or after a deploy.
- When the page opens it asks GitHub, with a very short timeout, for the newest published release: it says the installation is up to date, or shows the newer version linked to its release notes. If GitHub doesn't answer in time it says so and offers a "Check again" button that retries with more room. New admin manual in the three languages.

# Internal changes

## Staff newsletter format moved into CLAUDE.md:
- The format agreed for the staff newsletter (light, for rank-and-file teachers: everyone/CCFF-only split, concrete features only, an "Altres canvis rellevants" section for annoying fixes, links to each GitHub release) now lives in CLAUDE.md's "Staff newsletter email" section instead of only in one developer's agent memory, so every session follows it. Drafts are shown for approval before sending.

## CLAUDE.md: name the exact role, never a bare "chiefs"/"heads":
- New "Naming roles" section: always say Department Chief / Seminar Chief (department level) or Head of Studies / Deputy Head of Studies / Director / Secretary (management level), never a generic "chiefs", "heads" or "jefes", which had caused misunderstandings.
