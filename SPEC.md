<!-- SPDX-License-Identifier: Apache-2.0 -->

# AI Usage Disclosure (AID) — v0.1 (draft)

A vendor-neutral, machine-readable way for a software project to disclose
**how AI was used in building it**. It is informational, not a quality
judgment — a nutrition label, not a warning label.

It is deliberately *not*:
- a measure of code quality,
- a content-provenance standard for media the software emits,
- a detector. It is a **self-declared, good-faith disclosure** by the maintainer.

---

## 1. The manifest

A single file named `ai-usage.yml` at the repository root. Tooling and humans
read the same file. Filename is fixed so it can be discovered automatically
(the way `CITATION.cff`, `SECURITY.md`, and `LICENSE` are).

```yaml
version: "0.1"            # spec version
overall: collaborative    # one of the levels in §2 — the highest level across declared areas

areas:                    # per-area disclosure; omit an area to mean "not applicable"
  code:
    level: collaborative
    reviewed: true         # was AI-produced output in this area human-reviewed before merge?
  tests:
    level: assisted
    reviewed: false
  documentation:
    level: generated
    reviewed: false
  design:
    level: assisted
    reviewed: true
  assets: none             # shorthand: a bare level string when review status is N/A or unspecified

tools:                    # optional, free-form; helps reproducibility, not required
  - "Claude (Anthropic)"
  - "GitHub Copilot"

human_reviewed: false     # DERIVED summary — see §2.1. Do not set by hand.
disclosed_by: "Maintainer or org name"
updated: "2026-06-16"     # ISO 8601 date of last disclosure update
notes: >                  # optional free text
  Core logic hand-written; AI used for boilerplate, test scaffolding, and docs.
```

Only `version`, `overall`, and the per-area `level`s are required. Everything
else is optional, so the barrier to adoption is one short file.

Each area may be written in one of two forms:
- **bare string** — `assets: none` — just the level; review status unspecified.
- **map** — `code: { level: collaborative, reviewed: true }` — level plus a
  per-area `reviewed` flag.

`reviewed` is only meaningful when `level` is not `none` (there is no
AI output to review otherwise) and MUST be omitted or ignored for `none`.

---

## 2. The level taxonomy

A single ordinal scale, defined by **who authored the result**, applied both
overall and per-area. Neutral wording is intentional — no level implies "bad".

| Level           | Meaning |
|-----------------|---------|
| `none`          | No AI involvement in this area. |
| `assisted`      | AI provided autocomplete, suggestions, or answers; a human authored and decided the result. |
| `collaborative` | Significant portions were AI-generated, then human-edited, reviewed, and integrated. |
| `generated`     | Predominantly AI-generated with limited human modification. |

`overall` MUST equal the highest level present in `areas` (where
none < assisted < collaborative < generated). This keeps the headline honest:
a project with one `generated` area is not `assisted` overall.

### 2.1 Review status

Each area carries an optional `reviewed` boolean meaning **a human reviewed the
AI-produced output in that area before it was merged**. This is the trust
signal: a consumer can see that AI-written authentication code was reviewed
while AI-written docs were not, rather than guessing from one project-wide flag.

The top-level `human_reviewed` is a **derived summary**, not authored by hand:

> `human_reviewed` is `true` if and only if every area with AI involvement
> (`level` ≠ `none`) has `reviewed: true`. If any AI-involved area is
> unreviewed or its `reviewed` is unspecified, the summary is `false`.

This mirrors the `overall` rule — the headline can never claim more than the
detail supports.

### Recommended areas

`code`, `tests`, `documentation`, `design` (architecture/decisions),
`assets` (images, audio, etc.), `data`. Implementers may add areas; unknown
areas are valid and simply pass through.

---

## 3. The badge

A static shields.io badge derived from `overall`. Static = no runtime
service dependency, so it never breaks:

```markdown
[![AI Usage: <level>](https://img.shields.io/badge/AI_Usage-<level>-<color>)](./ai-usage.yml)
```

Suggested neutral palette (deliberately *not* a red→green "good/bad" gradient):

| Level           | Color hex |
|-----------------|-----------|
| `none`          | `9e9e9e`  |
| `assisted`      | `6fa8dc`  |
| `collaborative` | `5b8def`  |
| `generated`     | `7e57c2`  |

The badge MUST link to the repo's `ai-usage.yml` so the headline is always one
click from the detail. Because this is a static badge, maintainers MUST update
the badge when `overall` changes.

A dynamic variant (shields `endpoint` reading the YAML live) MAY be offered
later, but the static badge is the conformant default.

---

## 4. Conformance

A repository conforms to AID v0.1 if it contains a root `ai-usage.yml` that:
1. includes `version`, `overall`, and an `areas` map,
2. ensures every declared area has a valid `level`,
3. uses only defined levels,
4. sets `overall` to the maximum of its declared area levels, and
5. if `human_reviewed` is present, sets it per the derived rule in §2.1.

The badge is optional but recommended. Disclosure is the maintainer's
good-faith statement; the spec does not verify it.

---

## 5. Open design questions (for v0.2)

- **Auto-generation.** Some AI coding workflows can emit `Co-Authored-By:` /
  `Assisted-By:` commit trailers. A generator that reads trailers and proposes
  an `ai-usage.yml` is the single biggest lever for real adoption — it removes
  the manual-honesty burden.
- **Per-commit vs. per-project.** This spec is project-level. Line/commit-level
  attribution is complementary, not a replacement.
- **Naming.** "AID" / "AI Usage" are placeholders.
