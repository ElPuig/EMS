# Changes

## Erasmus+ polish: dates and numbers:

- Every date in the Erasmus+ backend screens shows the day alone (no hour, no seconds), with Odoo's own `show_time` option. Exceptions, on purpose: an editable deadline keeps its hour while editing (a date typed with no time would close it at midnight, a day early), and so do interviews, the turn to choose a destination and an offer's deadline. The portal still shows hours. Only the display changes.
- A 0 that means nothing is now an empty cell, with new widget `ems_blank_zero`: rates with no limit or any length of stay, staff figures of earlier courses with no data, diffusion actions whose reach isn't known. The stored value stays 0.
