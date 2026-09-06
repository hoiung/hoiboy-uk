# Runbook: partner brochure withdrawal (take-down + what git keeps)

Operator procedure for the consultancy partner named in the CRE and ICT services
brochure asking for her details to come down. The public promise this delivers is
the **Withdrawal** and **Retention** bullets of the `### Partnership brochure`
subsection in `content/legal/privacy/index.md`, and the lawful basis it satisfies
is consent under UK GDPR Article 6(1)(a) with explicit consent under Article
9(2)(a). Article 7(3) requires withdrawing to be as easy as agreeing was.

This repository is **public**. Deleting the file removes it from the live site but
leaves the brochure in git history, in every clone and in every fork. Section 4
below is what closes as much of that as is closeable, and says plainly what is not.

## Why this file exists

hoiboy-uk#59 Stage 5 simulated the withdrawal this notice promises and found the
repository's own CI would have blocked it. `tests/test_partner_disclosure_surfaces.py`
compared the set of surfaces naming her with the declared set using EQUALITY, so a
surface that stopped naming her failed the gate. Because `ci.yml` gates `deploy.yml`
and Cloudflare auto-build is disabled, a red CI means the deploy hook is never
posted and **the previous deployment keeps serving her data**. The gate written to
protect her would have been the thing keeping her published.

That is fixed: the comparison is now one-way, so removal is lawful and addition is
still caught. This runbook is the other half. A promise with no procedure behind it
is the same defect one level up.

## Before you start

- Confirm the request came from her, on a channel you can evidence.
- Decide the SCOPE with her, because two are meaningfully different:
  - **page only**: her name and description come off the ICT page, brochure stays.
  - **full**: brochure withdrawn as well.
- Record the request and the date. The consent record lives in the partnership
  folder of the private business repo, and the withdrawal belongs beside it.
  Her message does not go in the public Issue.

## 1. Take it off the live site

Work on a solo branch in a worktree, as usual.

**Page only**

Remove from `content/hire-hoi/ict-consultancy/_index.md` every sentence naming or
describing her. Then correct the notice, in BOTH passages, so it stops claiming the
page names her. `content/legal/privacy/index.md` states the same fact twice, at the
section-2 summary and in the section-4 subsection, and Stage 4 of #59 shipped a fix
to one and not the other. Check both.

**Full withdrawal**, additionally:

```bash
git rm static/hire-hoi/ict-consultancy/Jolyn-Hoi_CRE+ICT_brochure_v1.0.pdf
```

Then remove the `{{< static-link ... >}}` call and its heading from the ICT page,
the `Content-Disposition` rule from `static/_headers`, the `exclude:` line from
`.pre-commit-config.yaml`, and the `### Partnership brochure` subsection plus the
section-2 summary bullet from the notice.

The brochure link is guarded at BUILD time: `layouts/_shortcodes/static-link.html`
calls `errorf` when the file is missing, so removing the PDF without removing the
call fails `hugo` rather than shipping a dead link. That is the intended order of
discovery, not a problem.

## 2. Clear her name out of the repo's own files

These are not pages anyone navigates to, but the repository is public, so they
publish her name just as surely. They are declared in `DECLARED_REPO_SITES` in
`tests/test_partner_disclosure_surfaces.py`, which is the list to work from:

- `tests/test_gate_mutations.py` (the rows that prove the disclosure gate)
- `scripts/test_static_link_shortcode.py` (the shortcode contract fixture)
- `tests/test_partner_disclosure_surfaces.py` (the gate itself)
- `.pre-commit-config.yaml` and `static/_headers` (the brochure path)

On a full withdrawal, delete the partner-disclosure rows and the gate rather than
leaving them asserting against content that is gone.

## 3. Verify before you push

```bash
python3 -m pytest tests/test_partner_disclosure_surfaces.py -q
hugo --gc --minify -e production
grep -ril 'jolyn' content/ layouts/ static/ scripts/ tests/ .github/ .pre-commit-config.yaml
```

Expected: tests green, build exit 0, and the grep returning only what you
deliberately kept. A page-only withdrawal legitimately keeps the brochure hits.

Then push and confirm CI went green and `Deploy` actually ran. A merged commit is
not a deployed one: `deploy.yml` fires only on `workflow_run` with
`conclusion == 'success'`, so a red CI silently leaves the old page live. Check the
run, then fetch the live URL and confirm.

```bash
curl -sI https://hoiboy.uk/hire-hoi/ict-consultancy/Jolyn-Hoi_CRE+ICT_brochure_v1.0.pdf
curl -s  https://hoiboy.uk/hire-hoi/ict-consultancy/ | grep -ic jolyn
```

## 4. Git history, and what cannot be undone

Everything above changes the live site and the tip of `main`. None of it removes
the brochure or her name from history. Anyone can still read them at an older
commit, and every existing clone and fork already has them.

Closing that needs a history rewrite, which is a deliberate, separate operation
with real cost: it rewrites every commit after the file first landed, invalidates
every outstanding clone, and this repository's history is itself a portfolio
artefact. Do it only if she asks for it, and tell her honestly what it does and
does not reach.

Note the limit the notice does NOT claim to solve: commit `20aa19e`'s SUBJECT LINE
contains her name, and a blob-content purge does not rewrite commit subjects. A
full identity purge needs the subjects rewritten too.

Third-party forks, clones and caches are outside our control in every case. The
notice says so; do not promise otherwise when you reply to her.
