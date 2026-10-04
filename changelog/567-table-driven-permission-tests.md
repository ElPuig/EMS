# Internal changes

## Table-driven model access tests (141 repetitive permission tests removed):

- New `tests/test_access_matrix.py`: one table of model-level access rights (role → allowed
  read/write/create/unlink) checked with `has_access()` for every operation, 18 models and 36
  model/role pairs. It checks all four operations for each pair, more than the per-test checks
  it replaces did.
- Removed 109 `test_<role>_can/cannot_<op>` tests whose result depends only on
  `ir.model.access` (verified one by one against the real ACLs before removing them), and the 32
  "admin can create/write/unlink" tests that ran as the superuser and so checked no permission at
  all. Tests depending on record rules or on model-specific behaviour stay where they were.
- The three per-model "living data is frozen" tests became one test that checks every model in
  `_EMS_LIVING_CUSTOM_DATA_MODELS`, so a model added to that list is covered automatically.
- CLAUDE.md's backend testing convention now points new model-level access checks to the table.
