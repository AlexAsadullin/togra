"""Minimal ``.gitignore``-style pattern matcher.

Supported syntax (subset of git's spec):

* blank lines and lines starting with ``#`` are skipped;
* trailing ``/`` marks a directory-only pattern;
* leading ``/`` anchors the pattern to the project root;
* ``**`` matches any number of path components;
* ``*`` matches anything except ``/``;
* ``?`` matches a single non-``/`` char;
* a leading ``!`` negates the pattern.

The matcher walks patterns in order; the last one that matches wins, so a
later ``!pattern`` can re-include a file excluded by an earlier rule —
just like git.  Unsupported corner cases (character classes, ``\\``
escapes) are documented as a known limitation; we never silently misbehave.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True)
class _Rule:
    pattern: str
    negate: bool
    dir_only: bool
    anchored: bool
    regex: re.Pattern[str]


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Translate a (subset of) gitignore glob to a regex.

    We expand ``**`` ourselves because :func:`fnmatch.translate` collapses it
    to a single ``*``.  ``**/`` and ``/**`` both match "any number of
    intermediate path components".
    """
    # Tokenise around '**' so fnmatch.translate can handle the simple bits.
    out: list[str] = ["(?s:"]
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("/**", i):
            out.append("(?:/.*)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        else:
            # Consume the longest run that has no '**' so fnmatch can deal.
            j = pattern.find("**", i)
            chunk = pattern[i:] if j == -1 else pattern[i:j]
            # fnmatch.translate adds anchors / flags we don't want; strip.
            translated = fnmatch.translate(chunk)
            # Newer Pythons wrap as "(?s:...)\\Z"; strip both ends defensively.
            translated = re.sub(r"^\(\?s:", "", translated)
            translated = re.sub(r"\)\\Z\Z", "", translated)
            translated = re.sub(r"\\Z\Z", "", translated)
            out.append(translated)
            i = len(pattern) if j == -1 else j
    out.append(r")\Z")
    return re.compile("".join(out))


def _compile(line: str) -> _Rule | None:
    raw = line.rstrip("\n").rstrip("\r")
    stripped = raw.lstrip()
    if not stripped or stripped.startswith("#"):
        return None
    negate = False
    if stripped.startswith("!"):
        negate = True
        stripped = stripped[1:]
    dir_only = stripped.endswith("/")
    if dir_only:
        stripped = stripped[:-1]
    anchored = stripped.startswith("/")
    if anchored:
        stripped = stripped[1:]
    # An unanchored pattern with no slash matches at any depth — emulate
    # git's behaviour by prefixing "**/".
    if not anchored and "/" not in stripped:
        stripped = f"**/{stripped}"
    regex = _glob_to_regex(stripped)
    return _Rule(
        pattern=stripped,
        negate=negate,
        dir_only=dir_only,
        anchored=anchored,
        regex=regex,
    )


class IgnoreMatcher:
    """Compiled ``.tograignore`` ruleset."""

    def __init__(self, lines: list[str]):
        self._rules: list[_Rule] = []
        for line in lines:
            rule = _compile(line)
            if rule is not None:
                self._rules.append(rule)

    @classmethod
    def empty(cls) -> "IgnoreMatcher":
        return cls([])

    @classmethod
    def from_text(cls, text: str) -> "IgnoreMatcher":
        return cls(text.splitlines())

    def matches(self, rel_path: str, is_dir: bool = False) -> bool:
        """Return True if ``rel_path`` is ignored.

        ``rel_path`` must be POSIX-style and relative to the project root
        (use :meth:`pathlib.PurePosixPath.as_posix`).
        """
        path = str(PurePosixPath(rel_path))
        ignored = False
        for rule in self._rules:
            if rule.dir_only and not is_dir:
                # Directory-only rules don't match files directly, but they
                # do match files *inside* an ignored directory — handled by
                # iterating ancestors below.
                if not self._any_ancestor_match(rule, path):
                    continue
            if rule.regex.match(path):
                ignored = not rule.negate
            elif rule.dir_only and self._any_ancestor_match(rule, path):
                ignored = not rule.negate
        return ignored

    @staticmethod
    def _any_ancestor_match(rule: _Rule, path: str) -> bool:
        parts = path.split("/")
        for i in range(1, len(parts)):
            ancestor = "/".join(parts[:i])
            if rule.regex.match(ancestor):
                return True
        return False
