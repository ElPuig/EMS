# -*- coding: utf-8 -*-
"""Shared test utilities - see docs/en/developers/shared/testing.md for the rationale
(extracted after the DTON rollout found the same fixture/mock boilerplate hand-written
identically across dozens of test files)."""

import base64
import itertools
import json
import os
import time
from unittest.mock import patch

import werkzeug.urls

from odoo.tests.common import ChromeBrowser


_test_student_id_sequence = itertools.count(1)


def next_student_id():
    """A fresh Student ID (IDALU) for a test fixture student (issue #460).

    Every student-lifecycle contact needs one to be created, and it must be unique across the
    whole database, archived contacts included. The 'TEST' prefix can never match a real IDALU
    (digits only), so a fixture never collides with the development data test shards clone."""
    return f"TEST{next(_test_student_id_sequence):06d}"


def create_level_study(cls, prefix, **overrides):
    """Creates a level+study pair with `prefix`-derived unique codes.
    overrides: optional 'level'/'study' sub-dicts to override any field."""
    level = cls.env['ems.level'].create({
        'acronym': prefix, 'name': f'Test {prefix} Level', **overrides.get('level', {}),
    })
    study = cls.env['ems.study'].create({
        'code': f'{prefix}-01', 'acronym': prefix, 'name': f'Test {prefix} Study',
        'date': '2026-01-01', 'deprecated': False, 'level_id': level.id,
        **overrides.get('study', {}),
    })
    return level, study


def create_level_study_group(cls, prefix, **overrides):
    """Creates a level+study+group triple with `prefix`-derived unique codes.
    overrides: optional 'level'/'study'/'group' sub-dicts to override any field."""
    level, study = create_level_study(cls, prefix, level=overrides.get('level', {}), study=overrides.get('study', {}))
    group = cls.env['ems.group'].create({
        'course': 1, 'acronym': 'A', 'level_id': level.id, 'study_id': study.id,
        **overrides.get('group', {}),
    })
    return level, study, group


def mock_outgoing_email(cls):
    """Neutralizes real SMTP delivery for the duration of the test class - see CLAUDE.md's
    'Email safety in tests'. Call once from setUpClass. Returns the mock (e.g. to later assert
    on call count with cls.mail_transport.assert_not_called() / .reset_mock())."""
    patcher = patch(
        'odoo.addons.base.models.ir_mail_server.IrMailServer.send_email',
        return_value='test-message-id',
    )
    mock = patcher.start()
    cls.addClassCleanup(patcher.stop)
    return mock


def force_user_language_to_english(test, user):
    """Force `user`'s language to en_US for the duration of the current test only, restored
    via test.addCleanup() (on top of the test's own transaction rollback, for clarity since
    this mutates a real, pre-existing user rather than one created fresh in the test).

    Required by any tour/HttpCase test that logs in as a real, pre-existing account (e.g.
    base.user_admin, login="admin") and asserts on literal English button/field text - this
    box's real accounts are not guaranteed to have lang='en_US' (this dev DB's admin is
    'es_ES'), and a freshly created res.users record without an explicit 'lang' key isn't
    guaranteed en_US either (confirmed on this box: defaults to 'ca_ES'). See CLAUDE.md's
    "Tour tests and language" testing convention."""
    original_lang = user.lang
    user.lang = 'en_US'
    test.addCleanup(lambda: user.write({'lang': original_lang}))


def make_synchronous_run_in_thread(record):
    """A run_in_thread() replacement that runs setup/compute/store/callback synchronously
    against `record`, for tests that need run_action()'s wiring without real threading or a
    real LimesurveyApi call. Use as: patch.object(type(record), 'run_in_thread',
    side_effect=make_synchronous_run_in_thread(record), autospec=True)."""
    def fake_run_in_thread(self_record, setup, compute, store, callback, *args, **kwargs):
        setup(record)
        compute()
        store(record)
        callback(record)
    return fake_run_in_thread


# Maps a short role name to its ems.group_* xmlid - see security/groups.xml and
# docs/en/developers/employees/role_hierarchy.md for the full implication chain. Used by
# create_role_user() so tours/tests can log in as any EMS role without repeating xmlids.
ROLE_GROUP_XMLIDS = {
    'teacher': 'ems.group_teacher',
    'tutor': 'ems.group_tutor',
    'department_chief': 'ems.group_department_chief',
    'head_of_studies': 'ems.group_head_of_studies',
    'director': 'ems.group_director',
    'academic_admin': 'ems.group_academic_admin',
    'secretary': 'ems.group_secretary',
    'secretary_admin': 'ems.group_secretary_admin',
    'quality': 'ems.group_quality',
    'quality_admin': 'ems.group_quality_admin',
    'coexistence': 'ems.group_coexistence',
    'coexistence_admin': 'ems.group_coexistence_admin',
    'tac': 'ems.group_tac',
    'tac_admin': 'ems.group_tac_admin',
    'orientation': 'ems.group_orientation',
    'orientation_admin': 'ems.group_orientation_admin',
    'settings': 'ems.group_settings',
    'settings_admin': 'ems.group_settings_admin',
}


CORPORATE_TEST_DOMAIN = 'school.example.com'


def enforce_corporate_email_policy(cls, domain=CORPORATE_TEST_DOMAIN):
    """Makes res.company._ems_is_corporate_email() actually apply for the test class (issue
    #514): sets a fictitious Google Workspace domain on the company and declares the database a
    production one, since this dev box is 'ems.environment_type' = 'dev' (which skips the check)
    and CI's clean database has no value at all. Call once from setUpClass; both writes are
    rolled back with the class transaction."""
    cls.env.company.google_ws_domain = domain
    cls.env['ir.config_parameter'].sudo().set_param('ems.environment_type', 'production')


def create_role_user(cls, role, login, **overrides):
    """Creates a res.users with `role`'s group (see ROLE_GROUP_XMLIDS) plus base.group_user.

    'lang' is set to 'en_US' at creation - required by any tour asserting on English labels,
    since a freshly created res.users does not reliably default to en_US (see CLAUDE.md's "Tour
    tests and language"). `login` doubles as the password, matching start_tour()'s own
    convention. Extracted after the same ~15-line res.users.create() block was hand-written in
    9+ tour test files (e.g. test_student_data_reader_tour.py, test_employee_teacher_kanban_tour.py).

    overrides: any res.users field to override/add (e.g. 'name', 'email')."""
    vals = {
        'name': overrides.pop('name', f'Test {role.replace("_", " ").title()} User'),
        'login': login,
        'password': login,
        'lang': 'en_US',
        'groups_id': [
            (4, cls.env.ref('base.group_user').id),
            (4, cls.env.ref(ROLE_GROUP_XMLIDS[role]).id),
        ],
        **overrides,
    }
    return cls.env['res.users'].with_context(no_reset_password=True).create(vals)


def create_role_employee(cls, user, employee_type='teacher', **overrides):
    """Creates an hr.employee linked to `user`.

    `employee_type` defaults to 'teacher' since most EMS roles that need a paired employee
    (teacher, tutor, orientation, coexistence, tac - all imply ems.group_teacher) are teaching
    roles; pass employee_type='asp' for secretary/settings/quality-style roles. The '0000 '
    name prefix sorts first among the pre-existing teachers in this dev DB's list views, same
    trick used across the existing employee tours (e.g. test_employee_teacher_kanban_tour.py).

    overrides: any hr.employee field to override/add."""
    vals = {
        'name': overrides.pop('name', f'0000 {user.name}'),
        'employee_type': employee_type,
        'user_id': user.id,
        **overrides,
    }
    return cls.env['hr.employee'].create(vals)


def create_head_of_studies_branch(cls, prefix, tutor_employee):
    """Hangs `tutor_employee` below a Department Chief who hangs below a new Head of Studies
    (parent_id set directly, as the department cascade would), plus the people who must stay
    out of that tutor's scope: another Department Chief under the same Head of Studies and a
    second Head of Studies with nothing below them (issue #483). Sets cls.head_of_studies,
    cls.department_chief, cls.other_department_chief and cls.other_head_of_studies (res.users)."""
    key = prefix.lower()
    cls.head_of_studies = create_role_user(cls, 'head_of_studies', f'test_hos_{key}', name=f'{prefix} Head of Studies')
    head = create_role_employee(cls, cls.head_of_studies)
    cls.department_chief = create_role_user(
        cls, 'department_chief', f'test_chief_{key}', name=f'{prefix} Department Chief')
    tutor_employee.parent_id = create_role_employee(cls, cls.department_chief, parent_id=head.id)
    cls.other_department_chief = create_role_user(
        cls, 'department_chief', f'test_other_chief_{key}', name=f'{prefix} Other Department Chief')
    create_role_employee(cls, cls.other_department_chief, parent_id=head.id)
    cls.other_head_of_studies = create_role_user(
        cls, 'head_of_studies', f'test_other_hos_{key}', name=f'{prefix} Other Head of Studies')
    create_role_employee(cls, cls.other_head_of_studies)


def create_student_academic_file(cls, prefix, group, course=None, student=None):
    """Seeds the data the student form's Secretary and Academic history tabs render.

    An EMS enrolment is a `sale.order`, and the Secretary tab's authorizations are resolved
    from it by `res.partner._ems_enrollment_in_force()` - which reads the *running* course, so
    the enrolment has to hang off that one to be found. Returns a dict with every record, so a
    test can assert on any of them.

    Extracted after issue #393 needed the exact same fixture in a TransactionCase and in a tour.
    """
    Course = cls.env['ems.course']
    # Mirrors _ems_enrollment_in_force()'s own two-tier fallback exactly (is_current, then
    # is_enrollment_default) - a plain "first course found" fallback picked whichever course
    # sorts first under ems.course's own _order ('start desc', the LATEST one), which silently
    # never matches what that method falls back to (is_enrollment_default, seeded onto the
    # EARLIEST course when no course is current - see _ems_seed_enrollment_default) on a fresh
    # install with no current course configured. Found 2026-09-09 via CI: this enrolment's own
    # course never matched the one the Secretary tab's lookup resolved to, so it rendered empty
    # on a clean install despite passing on a dev database that already had a current course.
    course = course or Course.search([('is_current', '=', True)], limit=1) \
        or Course.search([('is_enrollment_default', '=', True)], limit=1) \
        or Course.create({'start': 2098, 'end': 2099})

    student = student or cls.env['res.partner'].create({
        'name': f'Test {prefix} Student', 'contact_type': 'student', 'student_id': next_student_id(),
        'student_email': f'test_{prefix.lower()}_student@example.com',
        'main_group_id': group.id,
    })

    order = cls.env['sale.order'].create({
        'partner_id': student.id, 'ems_study_id': group.study_id.id, 'ems_course_id': course.id,
    })
    # Creating the template applies it to every matching draft enrolment, which is what
    # produces the ems.authorization record the Secretary tab lists.
    template = cls.env['ems.authorization.template'].create({
        'name': f'Test {prefix} Image Rights', 'legal_text': '<p>Text</p>', 'auth_type': 'image',
    })
    authorization = order.ems_authorization_ids.filtered(
        lambda auth: auth.template_id == template)
    # Signing needs the PDF in the same write - see ems.authorization.write().
    authorization.write({'status': 'yes',
                         'signed_document': base64.b64encode(b'%PDF-1.4 test'),
                         'signed_document_name': 'signed.pdf'})

    benefit = cls.env['ems.student.benefit'].create({
        'student_id': student.id, 'benefit_type': 'scholarship',
        'document': base64.b64encode(b'%PDF-1.4 test'), 'document_name': 'test.pdf',
    })
    year_record = cls.env['ems.student.year_record'].create({
        'student_id': student.id, 'course_id': course.id,
    })
    return {'student': student, 'course': course, 'order': order, 'auth_template': template,
            'authorization': authorization, 'benefit': benefit, 'year_record': year_record}


class DocsScreenshotMixin:
    """Shared `_capture()` machinery for regenerating user-manual screenshots - extracted from
    `tests/test_docs_screenshots.py`'s original, private version once a second, per-role file
    needed the exact same method (see docs/en/developers/shared/testing.md). Mix into an
    `odoo.tests.common.HttpCase` subclass (needs `self.authenticate`, `self.cr`, `self.base_url()`,
    `self._wait_remaining_requests()`, `self._logger` - all HttpCase-provided).

    Writes PNGs to /tmp/ems_doc_screenshots (override with EMS_SCREENSHOT_DIR) - copy them into
    docs/assets/<role>/ by hand afterwards (the test runs as the `odoo` user, which has no write
    access to the repository). Every screenshot must use fixture data created in the test's own
    (rolled-back) transaction, never real data from this box - see CLAUDE.md's "Screenshots must
    never expose real personal data"."""

    OUTPUT_DIR = os.environ.get('EMS_SCREENSHOT_DIR', '/tmp/ems_doc_screenshots')

    @staticmethod
    def _trim(path, margin=6):
        """Crop the uniform background off the edges - an element's bounding box routinely
        includes a large empty area (an unfilled list, the rest of a form sheet) that only
        makes the image smaller in the manual."""
        from PIL import Image, ImageChops
        image = Image.open(path).convert('RGB')
        background = Image.new('RGB', image.size, image.getpixel((image.width - 1, image.height - 1)))
        box = ImageChops.difference(image, background).getbbox()
        if not box:
            return
        left, top, right, bottom = box
        image.crop((
            max(left - margin, 0), max(top - margin, 0),
            min(right + margin, image.width), min(bottom + margin, image.height),
        )).save(path)

    @staticmethod
    def _union_clip_js(selectors, element_id='ems-clip'):
        """JS that lays an invisible box over the union of `selectors`, so one shot can cover
        blocks that share no container of their own (clip to '#<element_id>' afterwards)."""
        return ("(function () { var old = document.getElementById(%s); if (old) { old.remove(); }"
                " var rects = %s.map(function (s) { return document.querySelector(s).getBoundingClientRect(); });"
                " var left = Math.min.apply(null, rects.map(function (r) { return r.left; }));"
                " var top = Math.min.apply(null, rects.map(function (r) { return r.top; }));"
                " var right = Math.max.apply(null, rects.map(function (r) { return r.right; }));"
                " var bottom = Math.max.apply(null, rects.map(function (r) { return r.bottom; }));"
                " var box = document.createElement('div'); box.id = %s;"
                " box.style.cssText = 'position:absolute;pointer-events:none;left:' + (left + scrollX) + 'px;top:'"
                " + (top + scrollY) + 'px;width:' + (right - left) + 'px;height:' + (bottom - top) + 'px';"
                " document.body.appendChild(box); })();"
                % (json.dumps(element_id), json.dumps(list(selectors)), json.dumps(element_id)))

    @staticmethod
    def _mouse_click(browser, selector):
        box = json.loads(browser._websocket_request('Runtime.evaluate', params={
            'expression': """JSON.stringify((function () {
                var r = document.querySelector(%s).getBoundingClientRect();
                return {x: r.x + r.width / 2, y: r.y + r.height / 2};
            })())""" % json.dumps(selector),
            'returnByValue': True,
        })['result']['value'])
        for event in ('mouseMoved', 'mousePressed', 'mouseReleased'):
            browser._websocket_request('Input.dispatchMouseEvent', params={
                'type': event, 'x': box['x'], 'y': box['y'], 'button': 'left', 'clickCount': 1,
            })

    MARK_RADIUS = 13

    def _draw_marks(self, browser, path, clip, marks):
        """Draws a numbered circle next to each marked element, in the style the manuals
        already used for their hand-made callouts. `anchor` places it relative to the element:
        'left' (default, just outside its left edge), 'right', 'top' (above its centre),
        'center', or 'text-right' (right after the element's text rather than its box - for a
        cell or a row that spans far wider than what it says)."""
        from PIL import Image, ImageDraw, ImageFont
        image = Image.open(path).convert('RGB')
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 14)
        radius = self.MARK_RADIUS
        for mark in marks:
            selector, label = mark[0], mark[1]
            anchor = mark[2] if len(mark) > 2 else 'left'
            rect = json.loads(browser._websocket_request('Runtime.evaluate', params={
                'expression': """JSON.stringify((function () {
                    var el = document.querySelector(%s);
                    if (!el) { return null; }
                    var r = el.getBoundingClientRect();
                    if (%s) {
                        // Union of the element's own text nodes only: a cell's box (or a child
                        // stretched to fill it) spans far wider than what it says.
                        var walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT), node,
                            left = Infinity, top = Infinity, right = -Infinity, bottom = -Infinity;
                        while ((node = walker.nextNode())) {
                            if (!node.textContent.trim()) { continue; }
                            var range = document.createRange();
                            range.selectNodeContents(node);
                            var t = range.getBoundingClientRect();
                            left = Math.min(left, t.left); top = Math.min(top, t.top);
                            right = Math.max(right, t.right); bottom = Math.max(bottom, t.bottom);
                        }
                        if (right > left) {
                            r = {x: left, y: top, width: right - left, height: bottom - top};
                        }
                    }
                    return {x: r.x, y: r.y, width: r.width, height: r.height};
                })())""" % (json.dumps(selector), json.dumps(anchor.startswith('text-'))),
                'returnByValue': True,
            })['result']['value'])
            self.assertTrue(rect, "mark selector matched nothing: %s" % selector)
            x, y = rect['x'] - clip['x'], rect['y'] - clip['y']
            centre = {
                'left': (x - radius - 4, y + rect['height'] / 2),
                'right': (x + rect['width'] + radius + 4, y + rect['height'] / 2),
                'text-right': (x + rect['width'] + radius + 6, y + rect['height'] / 2),
                'top': (x + rect['width'] / 2, y - radius - 2),
                'center': (x + rect['width'] / 2, y + rect['height'] / 2),
            }[anchor]
            cx = min(max(centre[0], radius + 1), image.width - radius - 2)
            cy = min(max(centre[1], radius + 1), image.height - radius - 2)
            draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
                         fill=(0, 229, 238), outline=(0, 0, 0), width=2)
            draw.text((cx, cy), str(label), fill=(0, 0, 0), font=font, anchor='mm')
        image.save(path)

    @staticmethod
    def _appear_code(selector):
        """JS that signals success once `selector` is on the page (plus a beat for the
        rendering to settle), and fails loudly rather than hanging if it never shows up."""
        quoted = json.dumps(selector)
        return """
            (function () {
                var attempts = 0;
                var timer = setInterval(function () {
                    attempts++;
                    if (document.querySelector(%s)) {
                        clearInterval(timer);
                        setTimeout(function () { console.log('screenshot ready'); }, 700);
                    } else if (attempts > 100) {
                        clearInterval(timer);
                        console.error('never appeared: ' + %s);
                    }
                }, 200);
            })();
        """ % (quoted, quoted)

    @staticmethod
    def _poll_for(browser, selector, timeout=20, interval=0.2, settle=0.7):
        """Python-side equivalent of `_appear_code`, for a wait that happens after the first
        one in the same browser instance - see the comment at its call site for why the
        browser's own success-future can't be reused for this."""
        deadline = time.time() + timeout
        quoted = json.dumps(selector)
        while time.time() < deadline:
            found = browser._websocket_request('Runtime.evaluate', params={
                'expression': 'document.querySelector(%s) !== null' % quoted,
                'returnByValue': True,
            })['result']['value']
            if found:
                time.sleep(settle)
                return
            time.sleep(interval)
        raise TimeoutError("never appeared: %s" % selector)

    def _capture(self, url_path, selector, filename, login=None, wait_for=None, padding=8,
                 click=None, run=None, wait_after=None, tour=None, max_height=None, marks=None,
                 beyond_viewport=True):
        """Load url_path as `login`, wait for `wait_for` (defaults to `selector`), optionally
        click `click` (or run arbitrary JS via `run`) and wait for `wait_after`, then write a
        PNG clipped to `selector` into OUTPUT_DIR.

        The click exists for a send/confirm assistant whose preview is built by an onchange,
        which opening the form with defaults does not fire on its own. max_height cuts the shot
        short, for a selector as big as the page whose empty lower part _trim() can't tell apart.
        login=None skips authentication entirely, for a page shown before signing in (e.g. the
        login screen itself) - there is no session to set up. `run` is a raw JS expression (or
        list of them, paired with `wait_after` the same way `click` is) for an interaction a
        plain `.click()` can't express - e.g. setting a <select>'s value and dispatching its own
        change event, needed for an OWL component that reacts to 'change' rather than a click.
        `marks` draws numbered callouts that a manual's text refers to ("click (1), then (2)"):
        a list of (selector, label) or (selector, label, anchor) - see _draw_marks().
        beyond_viewport=False for a shot of an open navbar section dropdown: capturing beyond the
        viewport makes Chrome resize the page, and Odoo closes that dropdown on the resize (the apps
        menu survives it). The clip must then lie inside the viewport (max_height keeps it short).
        """
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)
        # A tour reports success with Odoo's own signal ('tour succeeded', the one start_tour()
        # waits for); the plain wait for a selector uses ours.
        browser = ChromeBrowser(self, headless=True,
                                success_signal='tour succeeded' if tour else 'screenshot ready')
        try:
            if login:
                self.authenticate(login, login, browser=browser)
            else:
                # No session means no res.users.lang to render against - every other capture
                # gets Catalan from its fixture user's own lang, this is the one path that needs
                # it forced onto the request itself (the login page honours Accept-Language, not
                # the ?lang= query param - confirmed empirically).
                browser._websocket_request('Network.enable')
                browser._websocket_request('Network.setExtraHTTPHeaders',
                                           params={'headers': {'Accept-Language': 'ca'}})
            self.cr.flush()
            self.cr.clear()
            # A taller viewport than the default 1366x768, set BEFORE navigating so the page
            # lays out against it: anything below the fold renders as a grey band otherwise,
            # even with captureBeyondViewport.
            browser._websocket_request('Emulation.setDeviceMetricsOverride', params={
                'width': 1400, 'height': 1600, 'deviceScaleFactor': 1, 'mobile': False,
            })
            url = werkzeug.urls.url_join(self.base_url(), url_path)
            browser.navigate_to(url, wait_stop=True)
            if tour:
                browser._wait_ready('odoo.isTourReady(%s)' % json.dumps(tour))
                browser._wait_code_ok(
                    'odoo.startTour(%s, {stepDelay: 0, keepWatchBrowser: false, debug: false, '
                    'startUrl: %s, delayToCheckUndeterminisms: 0})'
                    % (json.dumps(tour), json.dumps(url_path)), timeout=120)
            else:
                browser._wait_code_ok(self._appear_code(wait_for or selector), timeout=60)
            if click or run:
                # click/run/wait_after each accept either one item or a list, for a sequence of
                # steps that each need their own settle before the next one fires (e.g. a pivot's
                # "Expand all" clicked twice, once per row level - found 2026-09-17 capturing the
                # attendance-reports pivot). click and run are mutually exclusive per call (pick
                # whichever fits the interaction), not mixed within the same list.
                steps = run if run else click
                steps = steps if isinstance(steps, (list, tuple)) else [steps]
                wait_afters = wait_after if isinstance(wait_after, (list, tuple)) else [wait_after] * len(steps)
                for step, step_wait in zip(steps, wait_afters):
                    if not run and step.startswith('mouse:'):
                        # A real (trusted) mouse click at the element's centre, for a control
                        # that ignores a synthetic .click() - e.g. the navbar's section dropdowns.
                        self._mouse_click(browser, step[len('mouse:'):])
                    else:
                        expression = step if run else 'document.querySelector(%s).click()' % json.dumps(step)
                        browser._websocket_request('Runtime.evaluate', params={'expression': expression})
                    # Not a second browser._wait_code_ok(): ChromeBrowser's own success future
                    # (self._result) is single-use, set once in __init__ and never reset - a SECOND
                    # call just re-reads the FIRST wait's already-resolved value instead of actually
                    # waiting again, so it returns near-instantly regardless of whether wait_after's
                    # own condition is true yet. Harmless for a click whose effect is a synchronous
                    # DOM update (already rendered by the time this line runs), but silently wrong
                    # for one that needs a server round-trip (e.g. opening a dialog whose defaults
                    # come from an onchange) - found 2026-09-17 capturing the "Request Correction"
                    # wizard, where the rect grab right after used to fail with a null selector
                    # because the dialog hadn't mounted yet. Poll from Python instead, which has no
                    # such single-use limitation.
                    self._poll_for(browser, step_wait or selector)
            rect = browser._websocket_request('Runtime.evaluate', params={
                'expression': """JSON.stringify((function () {
                    var el = document.querySelector(%s);
                    var r = el.getBoundingClientRect();
                    return {x: r.x, y: r.y, width: r.width, height: r.height};
                })())""" % json.dumps(selector),
                'returnByValue': True,
            })['result']['value']
            box = json.loads(rect)
            clip = {
                'x': max(box['x'] - padding, 0),
                'y': max(box['y'] - padding, 0),
                'width': box['width'] + padding * 2,
                'height': min(box['height'] + padding * 2, max_height or float('inf')),
                'scale': 1,
            }
            png = browser._websocket_request('Page.captureScreenshot', params={
                'clip': clip, 'captureBeyondViewport': beyond_viewport,
            }, timeout=30.0)['data']
            path = os.path.join(self.OUTPUT_DIR, filename)
            with open(path, 'wb') as handle:
                handle.write(base64.b64decode(png))
            if marks:
                self._draw_marks(browser, path, clip, marks)
            self._trim(path)
            self.assertGreater(os.path.getsize(path), 2000, "%s looks empty" % filename)
            self._logger.info("Wrote %s", path)
        finally:
            browser.stop()
            self._wait_remaining_requests()
