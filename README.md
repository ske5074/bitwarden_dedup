# bwclean3.py

Deduplicate a Bitwarden / Vaultwarden JSON vault export. Runs locally, no dependencies
outside the standard library, no network access.

Fork of [topisani/bwclean2.py](https://gist.github.com/topisani/066b63b87346afe76ffdf0998d4ebc2f)
(the JSON port), itself a fork of [serif/bwclean2.py](https://gist.github.com/serif/a1281c676cf5a1f77af6ff1a25255a85)
(the original CSV version, 2018). Credit for the approach goes to them; this fork fixes
three bugs that made the output non-idempotent.

## Usage

```
./bwclean3.py bitwarden_export.json
```

Writes two files next to the input:

- `bitwarden_export_out.json` — the deduplicated vault, ready to re-import
- `bitwarden_export_rem.json` — the items that were removed, for review

Re-running against `_out.json` should remove 0 items. If it doesn't, open an issue.

## What counts as a duplicate

Two **login items** are duplicates when they share any `(host, username, password)`
triple. Hosts come from every URI on the item, so an item with several URIs is matched
on all of them, and matching groups are merged transitively.

Everything else — secure notes, cards, identities, and logins with no URIs — is matched
on an exact content hash, ignoring `id`, `creationDate`, `revisionDate`, `deletedDate`
and `passwordHistory`. Only byte-identical items collapse.

When items match, the one with the newest `revisionDate` is kept.

## What this fork fixes

All three bugs were introduced by the CSV → JSON port and are present in both upstream
gists.

**1. Item fan-out.** v2 stored each item in `hash_items` once per URI, so
`list(hash_items.values())` emitted an item with N URIs N times. Running v2 on its own
output found hundreds of "duplicates" that were the same object repeated. On a
1758-item vault, v2 wrote 1126 items of which 201 were repeats. v3 groups per item and
unions the key sets when groups collide.

**2. URI-less items were never deduplicated.** v2 sent any item without `login.uris`
straight to `keep_items` untouched — every secure note, card, identity, Wi-Fi entry and
passkey-only login passed through verbatim, duplicates included. v3 falls back to the
content hash described above.

**3. Scheme-less URIs all collided.** `urlparse('jarvis').netloc` is `''`, as is
`urlparse('com.amazon.dee.app').netloc`, so every bare hostname, bare IP and Android
package ID hashed to the same empty host. Any two items sharing a username and password
plus one scheme-less URI were falsely merged. v3 falls back to `path` when `netloc` is
empty.

Also: the `_rem` file no longer contains items that are still present in `_out`, and the
report counts items rather than hash-table entries.

## Limitations

- **URIs are not merged.** The newest matching item is kept whole; extra URIs on the
  losing items are discarded, not appended to the survivor. Same for notes and custom
  fields. Review `_rem.json` before deleting it.
- **Folders are not deduplicated or pruned.**
- **Content matching is exact.** Two notes with the same name but one character
  different in the body stay separate. This is deliberate — under-merging is recoverable,
  over-merging destroys data.
- `collectionIds` is part of the content hash, so an identical note filed in two
  collections is not merged.
- Requires Python 3.9+ (uses the `|` dict merge operator).

## Optional: producing the export with the Bitwarden CLI

bwclean3 does **not** use the Bitwarden CLI — it reads a JSON file and writes two more,
so `bw` is not a requirement. You can export and re-import entirely from the web vault.
The CLI is just a faster way to do it, and it's scriptable.

### Install

Pick one:

```
npm install -g @bitwarden/cli          # requires Node.js
brew install bitwarden-cli             # macOS / Linuxbrew
choco install bitwarden-cli            # Windows
snap install bw                        # Linux
```

Bitwarden also publishes a standalone native executable if you'd rather not install
Node. Check the [CLI docs](https://bitwarden.com/help/cli/) for current platform support
and the minimum Node version.

### Export

```
bw login
export BW_SESSION="$(bw unlock --raw)"
bw sync
bw export --format json --output ./vault.json
```

`bw sync` first — the CLI works from a local cache, and without it you may export stale
data. For an organization vault, add `--organizationid`:

```
bw list organizations                  # find the id
bw export --organizationid <org-id> --format json --output ./vault.json
```

Only owners, admins and some custom roles can export organization items, and
organization exports are recorded in the event logs.

### Re-import

```
bw import bitwardenjson ./vault_out.json
```

Import **adds** items, it does not replace them — so importing without first purging the
vault will double everything you own. Purge from the web vault
(Settings → My account → Danger zone) after you've verified your backup, then import.

Note that CLI 2026.x added a master-password prompt for vault data operations, which can
break unattended scripts that previously ran clean.

### Caveats

- Exports exclude file attachments, items in the trash, and Sends.
- Individual vault exports do not include organization-owned data — they're separate
  exports and separate runs of this script.
- `bw lock` (or `bw logout`) when you're done, and unset `BW_SESSION`.

## Handling your export safely

A Bitwarden JSON export is **plaintext credentials**. Everything below matters more than
the script does.

1. Back up your vault before you change anything.
2. Work somewhere that isn't synced to cloud storage. A RAM disk is better than a disk.
3. Review `_rem.json` before you trust the result.
4. Purge your vault and re-import `_out.json` only once you're satisfied.
5. **Delete every `.json` file when you're done** — the original, the `_out`, the `_rem`.
   They can be read by any program running as your user.

## Alternatives

Other tools solving the same problem, several of which are better maintained:

- [elias123tre/bitwarden_find_duplicates](https://github.com/eliasfloreteng/bitwarden_find_duplicates)
  — browser-based, no Python needed; also the best index of tools in this space
- [jwmcgettigan/bitwarden_duplicate_cleaner.py](https://gist.github.com/jwmcgettigan/0bf7cd39947764896735997056ca74d7)
  — works through the Bitwarden CLI, no export file on disk
- [no84by/bitwarden-vault-cleanup](https://github.com/no84by/bitwarden-vault-cleanup)
  — actively maintained, merges related entries
- Discussion thread:
  [Duplicate removal tool / report (including merge)](https://community.bitwarden.com/t/duplicate-removal-tool-report-including-merge/648)

## License

Neither upstream gist carries an explicit license. This fork is published in the same
spirit — use it, change it, credit the original authors. Read the code before you run it
against your passwords.
