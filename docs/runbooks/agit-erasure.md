# Runbook: AGIT feature erasure (take-down + git-history purge)

Operator procedure for an AGIT community member asking for their published feature
to be taken down. The public promise this delivers is in
`content/legal/agit-story-guidelines/index.md` section 8, and the retention position
it satisfies is in `content/legal/privacy/index.md` (community-form Retention and
Article 17 bullets).

This repository is **public**. Deleting the page removes it from the live site but
leaves the member's photo, name and story in git history, in every clone, and in
every fork. The purge below is what closes that gap.

## Before you start

- Confirm the request came from the member, on the address in their submission record.
- Note the feature's bundle slug, e.g. `1-hoi-aka-hoiboy-ai-product-engineer`, and the
  Drive leaf name, which is the bundle's frontmatter `title` verbatim, e.g. `#1 Hoi aka Hoiboy`.
- **Order matters**: remove the Drive leaf FIRST. The Drive leaf name is read from the
  bundle's frontmatter, so once the bundle is deleted that name is no longer derivable.
  `agit_drive.py --remove` accepts an explicit `--leaf` for exactly this reason, but
  taking the ordering for granted is how a leaf gets orphaned.

## 1. Remove the Drive posting kit

```bash
# From agit-ops, with AGIT_DRIVE_ROOT set.
python3 scripts/agit_drive.py --remove --leaf '#1 Hoi aka Hoiboy'
```

Exits non-zero if the leaf holds files the exporter did not write; inspect rather than
force. An absent leaf is a logged no-op, not an error.

## 2. Remove the live page

Delete the feature bundle and its row, then deploy:

```bash
git rm -r content/community/agit-featured/<slug>/
# drop the feature's row from scripts/social-cards/agit-features.tsv
git commit -m "agit: take down feature <slug> at member request"
git push origin main
```

Confirm the page 404s and the community landing no longer lists the feature before
telling the member the live removal is done. That part is honest to report immediately;
the history purge below takes longer.

## 3. Purge the feature from git history

**This rewrites published history. Read the blast radius section first.**

Requires `git-filter-repo` (`pipx install git-filter-repo`). It refuses to run in a
clone that has other work in flight, which is deliberate.

```bash
# Work on a FRESH mirror clone, never your working clone.
git clone --mirror https://github.com/hoiung/hoiboy-uk hoiboy-uk-purge.git
cd hoiboy-uk-purge.git

# Strip the whole feature bundle from every commit that ever contained it.
git filter-repo --invert-paths \
  --path content/community/agit-featured/<slug>/

# Verify the member's files are gone from every ref.
git log --all --oneline -- content/community/agit-featured/<slug>/   # expect: no output
git rev-list --all --objects | grep '<slug>'                          # expect: no output

# Push the rewritten history.
git push --force --mirror
```

### Blast radius (know this before step 3)

- **Every commit SHA after the first touched commit changes.** Any link to a commit,
  any pinned SHA, any open PR branch is invalidated.
- **Every existing clone and fork keeps the old history.** Collaborators must re-clone;
  a `git pull` onto a rewritten history will not do the right thing.
- **GitHub keeps unreachable objects for a while.** Open a GitHub support request to
  purge the cache if the member needs the objects gone from GitHub's own serving,
  and say so plainly if they ask how complete the removal is.
- **Forks are separate repositories.** A purge on this repository does not touch them.
  If a fork exists, the honest answer to the member is that we have asked, not that we
  have removed.
- **Search-engine and archive caches** expire on their own schedule. Submit a removal
  request to the relevant engine if the member asks.
- Cloudflare Pages redeploys from the rewritten history; confirm the site still builds.

### What to tell the member

Confirm in writing: the live page is down (immediate), the Drive copy is deleted
(immediate), the history purge is done (same day where possible), and copies already
taken by third parties are outside our control. Do not claim more than that. The
guidelines page states the same limit, so the two must not disagree.

## 4. Record it

Keep the request and what was done in the member's record under `~/.agit-records/<slug>/`.
The Article 17(3)(e) legal-evidence basis in the Privacy Notice covers retaining the
erasure correspondence itself; it does not cover retaining the published feature.
