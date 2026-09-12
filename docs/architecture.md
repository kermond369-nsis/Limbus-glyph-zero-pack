# Architecture (CI/CD)

## Goal

Reproducible **零协 source → Android jp.zip** builds with a **self-maintained glyph map**, without trusting third-party re-packagers.

## Components

| Piece | Role |
|-------|------|
| `assets/font_ok.txt` | CJK set known displayable in the game JP slot |
| `assets/glyph_map.json` | source char → replacement string (may be multi-char) |
| `scripts/pack_zero_to_jp.py` | pure transform, no network |
| `.github/workflows/build-jp.yml` | fetch user-supplied archive → pack → artifact/release |

## Trust boundary

```
[User-hosted 零协 archive] --HTTPS--> [GitHub Actions]
                                         │
                                         ▼
                                   pack_zero_to_jp.py
                                   + assets/*
                                         │
                                         ▼
                                   jp.zip + sha256
```

- CI **does not** scrape captcha pages.
- CI **does not** store private keys.
- Game localization **is not** committed to this repo.
- Only tables + scripts + workflow are public.

## Why offline glyph map in git

Glyph conversion must be reviewable and reversible. Updating a map is a normal PR; it does not require shipping game text.

## Local parity

Same `pack_zero_to_jp.py` runs on developer machines and CI. Byte-identical inputs → same zip layout (timestamps may differ; compare file lists + content hashes if needed).

## Security / hygiene

- No credentials in workflow
- `permissions: contents: write` only for optional release publish
- Input URL must be HTTPS; operator is responsible for source legitimacy
- `.gitignore` blocks `*.p12`, `LimbusLocalize*`, env files

## Future (optional, not required)

- Matrix build for `jp` + `kr` prefixes
- Nightly job comparing `font_ok` drift when a new published pack is manually dropped as workflow input
- App pull of `jp.zip` from Releases with pinned SHA256
