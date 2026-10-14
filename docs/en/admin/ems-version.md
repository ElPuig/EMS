[Català](../../ca/admin/ems-version.md) | [Castellano](../../es/admin/ems-version.md) | [English](ems-version.md)

---

# Installed EMS version

The settings screen shows which EMS version is running on this installation, and whether a newer one has been published. Check it before reporting a problem, or to confirm that a new release has already been deployed.

**Required role:** Administrator

---

## Where to find it

Navigate to: **Settings → EMS Management**, at the bottom of the page, in the **About** block.

The **Installed version** field is read-only (e.g. `18.0.0.36.2`). It changes by itself every time EMS is updated; there is nothing to save.

---

## Is there a newer version?

Every time the page opens, EMS asks GitHub for the latest published version and shows one of these messages under the installed version:

| Message | What it means |
|---|---|
| **You are on the latest version.** | Nothing newer has been published. |
| **A newer version is available:** followed by its number | A newer version exists. The number links to its release notes on GitHub, which list everything it changes. Updating is done by whoever maintains the server. |
| **The latest version could not be checked.** | GitHub did not answer in time (the check waits only a moment so the page never slows down). Click **Check again**: the page reloads and waits a little longer. |

---

[← Back to Administrator index](index.md)
