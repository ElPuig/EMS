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
- Removed 43 per-model tests that only checked plain Odoo behaviour, each verified against the
  model first: 29 "missing field" tests on fields that are just `required=True`, 2 `display_name`
  tests on models whose name is simply `name`, and 12 "create a valid record" tests on models
  with no `create` override. Kept the ones testing EMS logic (own `display_name` computations,
  `create` overrides, constraints, computed values). `tests/test_space_type.py` was left with no
  test and was removed; the model stays covered by the access table and the admin smoke crawler.
- CLAUDE.md's backend testing convention now points new model-level access checks to the table
  and says what not to test (plain Odoo behaviour).
