# Technical Reference: form "Actions" dropdown

A form's actions on the record it shows live in **one "Actions" dropdown button in the header**, never as loose header buttons. Each entry is still an ordinary form button, so it keeps its own `invisible=`, `groups=` and `confirm=`: the dropdown only lists what applies to this record and this user, and it isn't rendered at all when nothing does.

It exists because neither native option covers the three needs at once:

| | Hidden per record state / per-user relationship | Visible to users | Header stays short |
|---|---|---|---|
| Native ⚙ cog menu (`binding_model_id` actions) | No: `get_bindings()` filters by `groups_id` and model read access only, never per record | No: users don't find it | Yes |
| Loose header buttons | Yes | Yes | No |
| **Actions dropdown** | Yes | Yes | Yes |

Used on the contact form (`views/community/contact/form.xml`) and the employee form (`views/community/employee/form.xml`); nothing in it is specific to either model.

## Usage

Put the buttons inside a `<div name="ems_actions" string="...">` directly under `<header>`:

```xml
<header>
    <div name="ems_actions" string="Actions">
        <button name="action_reset_google_password" type="object" string="Reset Google password"
                invisible="google_ws_state != 'active' or not can_reset_google_password"
                confirm="..." groups="ems.group_academic_admin,ems.group_tac,ems.group_tutor"/>
        ...
    </div>
</header>
```

Rules:

- **Every action goes in the dropdown**, including frequent ones and native ones: a loose header button is how the header filled up in the first place. Fields in the header (a statusbar, invisible helpers) stay outside the `div`.
- **Put the `div` in the form's own `<header>`** (`//header` `position="inside"`) when the inherited form already has one, rather than adding a second `<header>`: a form has one status bar.
- **Native header buttons** are moved in with an `<xpath ... position="move"/>` nested in an xpath on the `div`. The moving view must run after the one that adds the button: `view_employee_form_native_actions` has priority 130 because `hr_holidays_attendance` adds "Deduct Extra Hours" at 120, and `hr_holidays_attendance` is in EMS's `depends` so it is loaded first on a clean install. Match the button on an attribute that is neither translated (`string`) nor an action id resolved at load time (`name="%(xmlid)d"`), e.g. its `context`. A native button that is hidden for good (`invisible="1"`, like the employee's "Launch Plan") can stay where it is.
- **`type="object"`, not `type="action"`**, to run a bulk method on this one record. A form button of `type="action"` sends `active_ids` = the record's `resIds`, which can be the whole pager list rather than the record on screen. The bulk methods (`res.partner.action_portal_access_bulk()` etc.) already work on any recordset, a single record included.
- **Per-record permissions** go in a non-stored compute with `@api.depends_context('uid')` read by the entry's `invisible=` (e.g. `can_reset_google_password`, `can_download_google_credentials`), and the method re-checks them server-side. `groups=` alone only says the user holds a role, not that the role applies to this record.
- **The same action on the list** stays a cog-menu binding (`binding_view_types` = `list`), since there it acts on the selection. Don't also bind it to `form`: it would show twice.
- The `string` attribute is a view term, translated through the `.po` files like any other label.

## How it works

`static/src/js/backend/actions_dropdown.js` + `static/src/xml/backend/actions_dropdown.xml`:

- A `form_compilers` registry entry (Odoo's own extension point, the one `mail` uses for the chatter) compiles `div[name='ems_actions']` into an `EmsActionsDropdown` component, with one slot per compiled button. Each slot's `isVisible` is the button's compiled `t-if` (its `invisible=`); `groups=` are already stripped server-side.
- `EmsActionsDropdown` extends Odoo's `StatusBarButtons`, so it reuses `visibleSlotNames`. It renders a `Dropdown` (menu class `o_ems_actions_menu`) with one `DropdownItem` per visible slot (`o-dropdown-item-unstyled-button`, the same wrapping Odoo uses for header buttons folded into a menu), or nothing when no slot is visible.
- The component is added to `FormRenderer.components`, where the compiled form template resolves it.
- **Small screens:** Odoo already moves every header button into the cog menu there (`FormController` compiles the header a second time with `asDropdownItems`). A patch on `FormCompiler.compileHeader` unwraps the `div` in that pass, so its buttons become ordinary cog entries instead of a dropdown nested inside the cog menu.

## Testing

`static/tests/tours/actions_dropdown_helpers.js` holds the tour steps every tour needs to reach the entries: they only exist while the dropdown is open, and the open menu is rendered in the overlay container, outside `.o_form_view`. So a plain `.o_form_view button[name=...]` trigger never finds an entry, and a `:not(:has(button[name=...]))` check on the form passes whether it is offered or not.

- `clickAction(name, content)` opens the dropdown and clicks one entry.
- `checkActions({offered, notOffered}, content)` opens it, checks which entries it lists and closes it again. `offered` must not be empty: it is what proves the menu has rendered.
- `noActions(content)`: nothing applies, so no dropdown is rendered. With nothing else in the header, Odoo also leaves out the whole status bar.

`tests/test_actions_dropdown_tour.py` covers the component itself: as a tutor, which entries a real render offers for one of their students, that no button is left loose in the header, and that a family contact gets no dropdown; as an administrator on an employee with extra hours, that EMS's entries and the native "Deduct Extra Hours" share the one dropdown with nothing loose in the header.
