#!/usr/bin/env python3
# bwclean3.py - Bitwarden Duplicate Entry Remover v3
#
# Forked from topisani/bwclean2.py (JSON port)
#   https://gist.github.com/topisani/066b63b87346afe76ffdf0998d4ebc2f
# Originally serif/bwclean2.py (CSV, 2018)
#   https://gist.github.com/serif/a1281c676cf5a1f77af6ff1a25255a85
#
# Fixes three bugs introduced by the CSV->JSON port:
#
# 1. Item fan-out. v2 stored each item once per URI in hash_items, so
#    list(hash_items.values()) emitted an item with N URIs N times. A 1758-item
#    vault produced 1126 items, of which ~200 were repeats of the same objects.
#    v3 keys per item: all of an item's URI hashes form one group, and groups
#    merge when they share any key.
#
# 2. URI-less items never deduplicated. v2 sent items with no login.uris
#    straight to keep_items untouched - secure notes, cards, identities, and
#    Wi-Fi/passkey logins with empty uris arrays. v3 falls back to a hash of
#    the item's content (everything except id/dates/passwordHistory) so exact
#    copies collapse.
#
# 3. Scheme-less URIs collided. urlparse('jarvis').netloc is '', as is
#    urlparse('com.amazon.dee.app').netloc, so every Android package ID and
#    bare hostname hashed to the same empty domain. v3 falls back to path.
#
# Also: rem file no longer contains items still present in the out file, and
# the report counts items rather than hashes. Idempotent - a second pass over
# its own output removes 0.
import sys
import json
import hashlib
from urllib.parse import urlparse
from datetime import datetime

VOLATILE = {'id', 'creationDate', 'revisionDate', 'deletedDate', 'passwordHistory'}

def md5(s):
    return hashlib.md5(s.encode('utf-8')).hexdigest()

def host(uri):
    p = urlparse((uri or '').strip())
    return (p.netloc or p.path).strip('/').lower()

def keys(item):
    login = item.get('login') or {}
    cred = f"{login.get('username')}{login.get('password')}"
    ks = {md5(host(u.get('uri')) + cred) for u in (login.get('uris') or []) if host(u.get('uri'))}
    # no usable uri (secure notes, cards, uri-less logins): fall back to exact content
    return ks or {md5(json.dumps({k: v for k, v in item.items() if k not in VOLATILE},
                                 sort_keys=True, default=str))}

def rev(item):
    return datetime.fromisoformat((item.get('revisionDate') or '1970-01-01T00:00:00+00:00').replace('Z', '+00:00'))

def main(argv):
    if not argv:
        sys.exit('Supply input file path as command argument')

    in_path = argv[0]
    base = in_path.rsplit('.json', 1)[0]
    out_path, rem_path = base + '_out.json', base + '_rem.json'

    with open(in_path, encoding='utf8') as f:
        data = json.load(f)

    items = data['items']
    removed, groups, owner = [], [], {}

    for item in items:
        ks = keys(item)
        winner, merged = item, set(ks)
        # any group sharing a key is the same credential
        for gi in {owner[k] for k in ks if k in owner}:
            other, gkeys = groups[gi]
            merged |= gkeys
            loser = winner if rev(other) >= rev(winner) else other
            winner = other if loser is winner else winner
            removed.append(loser)
            groups[gi] = (None, set())
            print(f"duplicate: {loser.get('name')!r} ({loser.get('id')})")

        groups.append((winner, merged))
        for k in merged:
            owner[k] = len(groups) - 1

    uniq = [g[0] for g in groups if g[0] is not None]

    with open(out_path, 'w', encoding='utf8') as o, open(rem_path, 'w', encoding='utf8') as r:
        json.dump(data | {"items": uniq}, o, indent=4)
        json.dump(data | {"items": removed}, r, indent=4)

    print(f'\n{len(items)} total entries')
    print(f'{out_path}: {len(uniq)} kept')
    print(f'{rem_path}: {len(removed)} removed')

if __name__ == "__main__":
    main(sys.argv[1:])
