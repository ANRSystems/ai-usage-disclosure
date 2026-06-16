# AI Usage Disclosure (AID)

[![AI Usage: generated](https://img.shields.io/badge/AI_Usage-generated-7e57c2)](./ai-usage.yml)

AI Usage Disclosure is a small, vendor-neutral manifest for software projects to
disclose how AI was used during development. It is intended to be a transparency
label, not a quality score or detector.

## Files

- `SPEC.md` — draft v0.1 specification.
- `ai-usage.yml` — this repository's own disclosure manifest.
- `ai-usage-gen.py` — zero-dependency draft generator that scans git history for
  AI-attributed commit trailers and proposes an `ai-usage.yml`.

## Manifest example

```yaml
version: "0.1"
overall: collaborative
areas:
  code:
    level: collaborative
    reviewed: true
  tests:
    level: assisted
    reviewed: true
  documentation:
    level: generated
    reviewed: false
  assets: none
human_reviewed: false
tools:
  - "Claude (Anthropic)"
updated: "2026-06-16"
```

`overall` must equal the highest level present in `areas`:

`none < assisted < collaborative < generated`

`human_reviewed` is derived: it is true only when every AI-involved area has
`reviewed: true`.

## Generate a draft manifest

From inside a git repository:

```bash
python3 ai-usage-gen.py
```

To scan another repository and write the draft into that repository root:

```bash
python3 ai-usage-gen.py --repo ../target-repo --write
```

The generator writes evidence to stderr and keeps stdout clean for piping:

```bash
python3 ai-usage-gen.py > ai-usage.yml
```

Generated values are conservative drafts. Review the manifest before committing
it.

## Badge

Use a static badge linked to the repository's manifest:

```markdown
[![AI Usage: collaborative](https://img.shields.io/badge/AI_Usage-collaborative-5b8def)](./ai-usage.yml)
```

Update the badge whenever `overall` changes.

## Status

Draft v0.1. Names, fields, and conformance rules may change before a stable
release.

## License

Apache License 2.0. See [`LICENSE`](./LICENSE).

