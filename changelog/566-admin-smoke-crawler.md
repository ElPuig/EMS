# Internal changes

## Admin smoke crawler replaces the catalog create-and-save tours:

- New `TestRoleSmokeAdminTour`: the same crawler as the per-role smoke tours, logged in as a
  fixture user with every EMS administration group plus Director and Head of Studies, limited
  to EMS actions (`ems.*`). It opens every EMS screen an administrator reaches, in every view
  mode (98 views across 47 actions), and fails on any client error.
- Removed 15 tours that only created, edited or deleted a record with plain fields, all of them
  on screens the admin crawler now opens: employment types, job positions, work locations,
  providers, strike reasons, schedule frameworks, families, enrollment items, enrollment
  collections, enrollment templates, space types, non-teaching types, teaching reduction types,
  workgroups and spaces. Their create/save logic stays covered by the backend tests.
- Kept the catalog tours that check something of their own: levels and subjects ("Duplicate"
  not offered, tab contents), public holidays (a native action EMS customizes, outside the
  crawler's `ems.*` scope).
- Every smoke crawler now fails if it opened no action at all, and logs how many views and
  actions it covered.
