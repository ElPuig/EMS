#!/usr/bin/env python3
"""Spelling and grammar check of Catalan and Spanish texts with LanguageTool Premium.

Usage:
  scripts/i18n/lt_check.py FILE...                  .md or .po (msgstr only)
  scripts/i18n/lt_check.py --since v18.0.0.38.0     every ca/es text changed since a git ref
  scripts/i18n/lt_check.py --since HEAD FILE...     only the changed lines/entries of FILE
  scripts/i18n/lt_check.py --lang ca-ES --text "Vaig a faltar"

The language comes from the path (docs/ca/, ca_ES.po -> ca-ES; docs/es/, es_ES.po -> es-ES).
Markup (markdown syntax, link targets, code, HTML tags, Mermaid blocks, .po placeholders) is
sent to LanguageTool as markup, so only the prose is checked. Words listed in lt_ignore.txt
are never reported.

Credentials are personal and never in the repo: ~/.claude/languagetool.json with
{"username": "<account email>", "apiKey": "<key>"}. Without that file the script says so and
exits 0, so nobody without a key is blocked. Exit code 1 when there are findings.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = 'https://api.languagetoolplus.com/v2/check'
CREDENTIALS = os.path.expanduser('~/.claude/languagetool.json')
IGNORE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lt_ignore.txt')
CHUNK = 20000  # characters per request
CHECKED_PATHS = re.compile(r'^(docs/(ca|es)/.+\.md|i18n/(ca|es)_ES\.po)$')
# Rules that only fire on what the markup conversion can't hide.
DISABLED_RULES = ['WHITESPACE_RULE', 'UNPAIRED_BRACKETS', 'CONFUSIONS_EMS']
# A msgstr is often a fragment (a label, the tail of a sentence): no capital or final stop needed.
PO_DISABLED_RULES = ['UPPERCASE_SENTENCE_START', 'PUNT_FINAL']

MD_MARKUP = re.compile(r'''
    (?P<fence>^```.*?^```[^\n]*$)                       # fenced code / mermaid
  | (?P<front>\A---\n.*?\n---\n)                        # front matter
  | (?P<comment><!--.*?-->)
  | (?P<code>`[^`\n]+`)
  | (?P<img>!\[[^\]]*\]\([^)]*\))
  | (?P<linkend>\]\([^)]*\))                            # "](url)" of a link
  | (?P<linkstart>\[)(?=[^\]]*\]\()
  | (?P<html></?[A-Za-z][^>]*>)
  | (?P<url>https?://\S+)
  | (?P<head>^\#{1,6}[ \t]+)
  | (?P<list>^[ \t]*(?:[-*+]|\d+\.)[ \t]+)
  | (?P<quote>^[ \t]*>[ \t]?(?:\[![A-Z]+\])?)
  | (?P<table>^[ \t]*\|?(?:[ \t]*:?-{3,}:?[ \t]*\|)+[ \t]*:?-*:?[ \t]*$|\|)
  | (?P<emph>\*\*|__|(?<![\w*])\*(?!\s)|(?<!\s)\*(?![\w*]))
''', re.M | re.S | re.X)

BLOCK_TAG = re.compile(r'</?(br|p|div|li|ul|ol|table|tr|td|th|h\d)\b', re.I)
PO_MARKUP = re.compile(r'%\([^)]+\)[sdf]|%[sdf]|\{[^{}]*\}|<[^>]+>|&[a-z]+;|https?://\S+')


def language_of(path):
    return 'es-ES' if re.search(r'(^|/)docs/es/|es_ES\.po$', path) else 'ca-ES'


def annotate(text, pattern):
    """Split text into LanguageTool 'data' annotations: prose as text, the rest as markup."""
    parts, pos = [], 0
    for match in pattern.finditer(text):
        if match.start() > pos:
            parts.append({'text': text[pos:match.start()]})
        markup = match.group(0)
        if '\n' in markup or markup.startswith(('#', '|', '```')):
            interpret = '\n\n'  # a block boundary
        elif markup.startswith(('`', '%', '{')):
            interpret = '0'  # inline code or placeholder: a neutral token
        elif BLOCK_TAG.match(markup):
            interpret = ' '  # inline tags (<b>, <em>, <span>...) separate nothing
        else:
            interpret = ''
        parts.append({'markup': markup, 'interpretAs': interpret} if interpret else {'markup': markup})
        pos = match.end()
    if pos < len(text):
        parts.append({'text': text[pos:]})
    return parts


def chunks(parts):
    """Group annotations into requests of at most CHUNK characters, with their start offset."""
    batch, size, offset, start = [], 0, 0, 0
    for part in parts:
        length = len(part.get('text', part.get('markup', '')))
        if batch and size + length > CHUNK and 'text' in part:
            yield start, batch
            batch, size, start = [], 0, offset
        batch.append(part)
        size += length
        offset += length
    if batch:
        yield start, batch


class Checker:

    def __init__(self, credentials, picky=False):
        self.credentials = credentials
        self.picky = picky
        self.ignored = set()
        if os.path.exists(IGNORE_FILE):
            with open(IGNORE_FILE, encoding='utf-8') as handle:
                self.ignored = {line.strip() for line in handle if line.strip() and not line.startswith('#')}

    def _request(self, parts, lang, disabled):
        payload = urllib.parse.urlencode({
            'data': json.dumps({'annotation': parts}),
            'language': lang,
            'level': 'picky' if self.picky else 'default',
            'disabledRules': ','.join(DISABLED_RULES + disabled),
            'username': self.credentials['username'],
            'apiKey': self.credentials['apiKey'],
        }).encode()
        for attempt in range(4):
            try:
                with urllib.request.urlopen(API, payload, timeout=60) as response:
                    return json.load(response)['matches']
            except urllib.error.HTTPError as error:
                if error.code in (429, 503) and attempt < 3:
                    time.sleep(10 * (attempt + 1))
                    continue
                sys.exit(f'LanguageTool HTTP {error.code}: {error.read()[:300]!r}')

    def check(self, text, pattern, lang, disabled=()):
        """Findings in text, each with its absolute offset."""
        findings = []
        for start, batch in chunks(annotate(text, pattern)):
            for match in self._request(batch, lang, list(disabled)):
                offset = start + match['offset']
                word = text[offset:offset + match['length']]
                if word.strip(' .,;:*') in self.ignored:
                    continue
                findings.append({
                    'offset': offset, 'word': word, 'rule': match['rule']['id'],
                    'message': match['message'],
                    'replacements': [r['value'] for r in match['replacements'][:3]],
                })
        return findings

    def check_markdown(self, path, lines=None):
        """lines: only report findings on these line numbers (None = all)."""
        with open(path, encoding='utf-8') as handle:
            text = handle.read()
        findings = []
        for finding in self.check(text, MD_MARKUP, language_of(path)):
            line = text.count('\n', 0, finding['offset']) + 1
            if lines is None or line in lines:
                findings.append(dict(finding, where=f'{path}:{line}'))
        return findings

    def check_po(self, path, previous=None):
        """previous: {msgid: msgstr} of an older version; only new or changed msgstr are checked."""
        import polib
        entries = [entry for entry in polib.pofile(path) if entry.msgstr and not entry.obsolete
                   and (previous is None or previous.get(entry.msgid) != entry.msgstr)]
        # One request for many entries: join them as paragraphs and map offsets back.
        text, spans = '', []
        for entry in entries:
            spans.append((len(text), len(text) + len(entry.msgstr), entry))
            text += entry.msgstr + '\n\n'
        findings = []
        for finding in self.check(text, PO_MARKUP, language_of(path), PO_DISABLED_RULES):
            for begin, end, entry in spans:
                if begin <= finding['offset'] < end:
                    findings.append(dict(finding, where=f'{path}:{entry.linenum}'))
                    break
        return findings


def git(*args):
    return subprocess.run(['git', *args], capture_output=True, text=True, check=False).stdout


def changed_lines(path, ref):
    """Line numbers of path added or modified since ref; None when the file is new."""
    if subprocess.run(['git', 'cat-file', '-e', f'{ref}:{path}'], capture_output=True, check=False).returncode:
        return None
    lines = set()
    for hunk in re.finditer(r'^@@ -\S+ \+(\d+)(?:,(\d+))? @@', git('diff', '-U0', ref, '--', path), re.M):
        first, count = int(hunk.group(1)), int(hunk.group(2) or 1)
        lines.update(range(first, first + count))
    return lines


def previous_po(path, ref):
    import polib
    content = git('show', f'{ref}:{path}')
    return {entry.msgid: entry.msgstr for entry in polib.pofile(content)} if content else {}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('files', nargs='*')
    parser.add_argument('--since', metavar='REF', help='only what changed since this git ref')
    parser.add_argument('--text', help='check this text instead of files')
    parser.add_argument('--lang', default='ca-ES', help='language of --text (ca-ES, es-ES)')
    parser.add_argument('--picky', action='store_true', help='also style suggestions')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()

    if not os.path.exists(CREDENTIALS):
        print(f'lt_check: no LanguageTool credentials ({CREDENTIALS}), nothing checked.', file=sys.stderr)
        return 0
    with open(CREDENTIALS, encoding='utf-8') as handle:
        checker = Checker(json.load(handle), args.picky)

    files = args.files
    if args.since and not files:
        files = [path for path in git('diff', '--name-only', args.since, '--').split() if CHECKED_PATHS.match(path)]
        files += [path for path in git('ls-files', '--others', '--exclude-standard').split()
                  if CHECKED_PATHS.match(path)]

    findings = []
    if args.text:
        findings += [dict(f, where='text') for f in checker.check(args.text, MD_MARKUP, args.lang)]
    for path in files:
        if not os.path.exists(path):
            continue
        if path.endswith('.po'):
            findings += checker.check_po(path, previous_po(path, args.since) if args.since else None)
        else:
            findings += checker.check_markdown(path, changed_lines(path, args.since) if args.since else None)

    if args.json:
        json.dump(findings, sys.stdout, ensure_ascii=False, indent=1)
    else:
        for finding in findings:
            suggestion = ' / '.join(finding['replacements']) or '-'
            print(f"{finding['where']}: «{finding['word']}» -> {suggestion}  [{finding['rule']}] {finding['message']}")
    return 1 if findings else 0


if __name__ == '__main__':
    sys.exit(main())
