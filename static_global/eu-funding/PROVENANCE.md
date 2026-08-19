# EU emblem assets - provenance

These files are the **official** "Funded by the European Union" emblem, downloaded
from the European Commission's logo download centre:

<https://ec.europa.eu/regional_policy/information-sources/logo-download-center_en>

Direct sources (downloaded 2026-08-19):

- <https://ec.europa.eu/regional_policy/sources/information-sources/logo-download-center/funded_en.zip>
- <https://ec.europa.eu/regional_policy/sources/information-sources/logo-download-center/funded_fr.zip>
- <https://ec.europa.eu/regional_policy/sources/information-sources/logo-download-center/funded_nl.zip>

Each file here is a byte-for-byte copy of a file from those archives; only the
name was changed. Nothing was redrawn, recoloured, cropped, rescaled or
re-typeset.

| File in this directory      | Original path inside the archive                                  | SHA-256 |
|-----------------------------|-------------------------------------------------------------------|---------|
| `eu-funded-en.png`          | `funded_EN/horizontal/RGB/PNG/EN_FundedbytheEU_RGB_POS.png`       | `d075e964f944e97fbc543ef883415da8397a1fe148c324724612109dc7735375` |
| `eu-funded-en-negative.png` | `funded_EN/horizontal/RGB/PNG/EN_FundedbytheEU_RGB_NEG.png`       | `33ab3e480137737b84567345f5ec62f14933ab3e1514a3869fd7d4bac397c44b` |
| `eu-funded-fr.png`          | `funded_FR/horizontal/RGB/PNG/FR_FundedbytheEU_RGB_POS.png`       | `0e56d6c2c08c8b6e114209dc2e82372f8750806f7b642685a3ce8a8b023dcddc` |
| `eu-funded-fr-negative.png` | `funded_FR/horizontal/RGB/PNG/FR_FundedbytheEU_RGB_NEG.png`       | `0a73f5132bee37d23404f7da490f597386d600c6c1ca9e17df6e8f5c1245de14` |
| `eu-funded-nl.png`          | `funded_NL/horizontal/RGB/PNG/NL_FundedbytheEU_RGB_POS.png`       | `cf6e44f6e77bad687e1bffc8ae1f02d5251d3a4fffccf362d2c8fa416d778d99` |
| `eu-funded-nl-negative.png` | `funded_NL/horizontal/RGB/PNG/NL_FundedbytheEU_RGB_NEG.png`       | `0d099ff04dbf17312b3e42173155ded51bf099bc52345eb68d082ae6fd7240aa` |

All are the **horizontal, RGB** version, 919 px high. `POS` (no suffix here) is
the positive/colour version for light backgrounds; `NEG` (`-negative`) is the
Commission's own version for dark backgrounds - white lettering, emblem still in
colour. Use the one that matches the background; do not apply CSS filters,
`mix-blend-mode`, borders or any other treatment to either.

## Why PNG and not SVG

The Commission's packages ship EPS, JPEG and PNG only - there is no SVG of the
combined emblem + funding statement. Converting the EPS would re-render and
re-typeset the asset, which the emblem rules forbid, so the official PNG is used
as-is. It is 4125 px wide, which is ample for any on-screen use.

## Rules to respect when using these files

See <https://commission.europa.eu/document/download/3192a0ef-6bda-4e1a-81ca-65ade2ffad73_en?filename=eu-emblem-rules_en.pdf>.
In short: never modify the emblem, never add anything on top of or inside it,
keep clear space around it, keep it at least 40 px high on screen, and never
display it on a site that is not genuinely EU-funded.
