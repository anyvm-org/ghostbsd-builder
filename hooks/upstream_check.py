#!/usr/bin/env python3
# Print the newest GhostBSD amd64 release version, e.g. "26.1". Empty
# output means "nothing detected" and is not an error; a non-zero exit
# means detection itself is broken (network error, HTTP error, or a page
# that no longer matches the expected shape) and must be reported by the
# caller, never swallowed. A failure must NEVER print a plausible-but-
# wrong version -- the version is only printed after every step below has
# succeeded.
#
# Source of truth: https://download.ghostbsd.org/releases/amd64/
# (this is the exact directory conf/ghostbsd-*.conf's VM_ISO_LINK points
# into, e.g. ".../releases/amd64/26.1-R15.0p2/GhostBSD-26.1-R15.0p2.iso").
#
# Fetched and confirmed by hand (2026-07-26): the directory is a plain
# Apache-style autoindex, one row per release directory. Two different
# naming eras coexist in the same listing:
#   <a href="24.04.1/">24.04.1/</a>   -- old dated scheme, "YY.MM[.N]"
#   <a href="24.10.1/">24.10.1/</a>
#   <a href="25.01-R14.2p1/">25.01-R14.2p1/</a>  -- current scheme:
#   <a href="26.1-R15.0p2/">26.1-R15.0p2/</a>       "<major>.<minor>-R<FreeBSD-base-version>"
#   <a href="latest/">latest/</a>     -- symlink, not a version
# conf/*.conf's VM_RELEASE only ever carries the bare "<major>.<minor>"
# prefix (e.g. "26.1", never "26.1-R15.0p2"), so the pattern captures just
# that leading two-part number and requires either nothing after it or the
# "-R<digits.digits>[p<digits>]" suffix, right before the closing "/" --
# this also means a three-part OLD-style dir like "24.04.1/" or
# "20.08.04/" can never match (the extra ".N" segment does not fit either
# alternative), which is correct: those historical builds do not use the
# current VM_RELEASE numbering and must never be picked. At fetch time the
# newest real release was 26.1 (dir "26.1-R15.0p2", 2026-04-18), matching
# the current conf/ghostbsd-26.1*.conf files.
#
# stdlib only (urllib.request, re, sys, os) -- no external dependencies.

import os
import re
import sys
import urllib.request

URL = "https://download.ghostbsd.org/releases/amd64/"
TIMEOUT = 60
USER_AGENT = "anyvm-org-upstream-watcher/1.0"

# Bare "X.Y/" or "X.Y-R<digits.digits>[p<digits>]/" only -- a three-part
# legacy dated dir ("24.04.1/") cannot satisfy either alternative and is
# correctly excluded.
PATTERN = re.compile(r'href="(\d+\.\d+)(?:-R[\d.]+(?:p\d+)?)?/"')


def resolve_natural_key():
    """Return the engine's own natural_key, or fail loudly.

    watch.yml clones base-builder INTO the builder repo root, so at
    detection time it sits at "base-builder/" (relative to this hook's
    cwd, the builder repo root). A local checkout instead has it as a
    sibling, "../base-builder". Try both, in that order.

    There is deliberately NO local fallback copy. Ordering must be the
    single rule the engine uses -- a per-hook duplicate would have to be
    kept in sync by hand across every builder and would drift silently,
    and a hook that ranks versions differently from watch.py is worse
    than one that refuses to run. Both real contexts (CI and a local
    sibling checkout) always provide base-builder, so an ImportError here
    means the environment is wrong: report it as broken detection rather
    than guessing an order.
    """
    for candidate in ("base-builder", os.path.join("..", "base-builder")):
        if not os.path.isdir(candidate):
            continue
        path = os.path.abspath(candidate)
        if path not in sys.path:
            sys.path.insert(0, path)
        try:
            import gendata
            return gendata.natural_key
        except ImportError:
            continue
    raise ImportError(
        "base-builder/gendata.py not importable from %s; expected it at "
        "./base-builder (CI) or ../base-builder (local checkout)"
        % os.getcwd())


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read().decode("utf-8", "replace")


def main():
    try:
        key = resolve_natural_key()
    except ImportError as e:
        sys.stderr.write("upstream_check: %s\n" % e)
        return 1
    try:
        html = fetch(URL)
    except Exception as e:
        sys.stderr.write("upstream_check: fetch of %s failed: %s\n"
                         % (URL, e))
        return 1
    versions = PATTERN.findall(html)
    if not versions:
        sys.stderr.write("upstream_check: no release directory found in "
                         "%s; page shape may have changed\n" % URL)
        return 1
    newest = sorted(set(versions), key=key)[-1]
    print(newest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
