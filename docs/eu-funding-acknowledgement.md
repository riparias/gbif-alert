# EU funding acknowledgement (for instance operators)

## Who this is for

**Only operators of instances that are genuinely funded by the European Union.**

If your instance is not EU-funded, stop here: leave `SHOW_EU_FUNDING_ACKNOWLEDGEMENT`
at its default (`False`) and put nothing from this page on your site. Displaying
the EU emblem without EU funding is a false claim of support, and appropriating
the emblem is explicitly forbidden by Article 17.2 of the Horizon Europe Grant
Agreement.

If your instance *is* EU-funded, the acknowledgement is an **obligation**, not a
courtesy: Article 17 requires every result funded by the grant - software
included - to display the EU emblem, a funding statement and a disclaimer.
Non-compliance can lead to a reduction of the grant (Art. 17.5 -> Art. 28).

Note the distinction this repository makes:

- The **repository** (README, `CITATION.cff`) acknowledges the funding of the
  GBIF Alert *software*. That is done once, for everyone, and needs nothing from
  you.
- A **running instance** acknowledges the funding of *that instance*. That is
  what this page is about, and it is opt-in per instance.

## What goes where

| Placement | Form | How |
|---|---|---|
| Footer, every page | Short: emblem + "Funded by the European Union" (the wording is typeset in the emblem) + a link to your "about this site" page | Set `SHOW_EU_FUNDING_ACKNOWLEDGEMENT=True` in your `.env`. Nothing else to do - the markup ships with the application. |
| "About this site" page | Long: emblem + funding statement + full disclaimer + your project name and grant number | Paste one of the snippets below into the page content (see next section). |

The full disclaimer is not required in the footer as long as it is one click
away - which is why the footer emblem links to the "about this site" page.

### The footer setting

```
SHOW_EU_FUNDING_ACKNOWLEDGEMENT=True
```

Restart the stack afterwards (`docker compose up -d`). The footer then shows the
official emblem, in the language the visitor is browsing in (English, French or
Dutch), using the Commission's own file for that language. Nothing about it is
instance-specific, so there is nothing to configure beyond the flag.

### The "about this site" page

That page is per-instance content, edited by hand in the Django admin. It is
**not** a file in this repository:

1. Log in to `/admin` on your instance.
2. Go to **Page fragments** and open the fragment whose identifier is
   **`about_this_site_page_content`** (create it if it does not exist yet).
3. Paste the snippet for your project at the end of the **`Content <language>`**
   field - `content_en`, `content_fr` or `content_nl` - and save.

The field is Markdown, and the renderer passes raw HTML through, so the `<img>`
tags below work as written (the explicit `width` is what keeps the emblem at a
sensible size).

The page fragment has one field per language and is not language-switched
automatically the way the footer is: fill in the field for your instance's
primary language, and use the emblem file that matches it
(`eu-funded-en.png`, `eu-funded-fr.png` or `eu-funded-nl.png`). A multilingual
instance should fill in the other language fields too, each with its own
matching emblem.

## Ready-to-paste snippets

### GuardIAS instance

```markdown
## Funding

<img src="/static/eu-funding/eu-funded-en.png" alt="Funded by the European Union" width="280">

This site is operated as part of the GuardIAS project, funded by the European Union's Horizon
Europe research and innovation programme under grant agreement No 101181413.

Funded by the European Union. Views and opinions expressed are however those of the author(s)
only and do not necessarily reflect those of the European Union or the European Research
Executive Agency (REA). Neither the European Union nor the granting authority can be held
responsible for them.
```

### OneSTOP instance

```markdown
## Funding

<img src="/static/eu-funding/eu-funded-en.png" alt="Funded by the European Union" width="280">

This site is operated as part of the OneSTOP project, funded by the European Union's Horizon
Europe research and innovation programme under grant agreement No 101180559.

Funded by the European Union. Views and opinions expressed are however those of the author(s)
only and do not necessarily reflect those of the European Union or the European Research
Executive Agency (REA). Neither the European Union nor the granting authority can be held
responsible for them.
```

### For any future EU-funded instance

Take either snippet, swap the project name and the grant number, and keep
everything else identical - in particular the disclaimer, which is prescribed
word-for-word by the Grant Agreement (Art. 17.3) and must not be paraphrased or
shortened.

Name **only your own grant** in an instance's snippet. Several grants are
acknowledged with a single emblem and a single funding statement, listing the
grant numbers in the accompanying text - never with two flags.

## Rules to respect

From Art. 17.2 and the Commission's
[emblem guidelines](https://commission.europa.eu/document/download/3192a0ef-6bda-4e1a-81ca-65ade2ffad73_en?filename=eu-emblem-rules_en.pdf):

- **One emblem only**, never two flags, whatever the number of grants.
- **No modification and no merging**: nothing added inside or on top of the
  emblem - no project acronym, no border, no recolouring, no CSS filter, no
  `mix-blend-mode`.
- **Protection zone**: keep clear space around the emblem, free of other logos,
  text or images.
- **Minimum size**: 1 cm high in print, and do not go below roughly 40 px high
  on screen.
- **Prominence**: where other logos appear alongside (project or institutional
  logos, GBIF), the EU emblem must be at least as large and as visible as the
  largest of them.
- **Spell out "European Union"** - never "EU", no all-caps, no underline. The
  official emblem files already carry the statement typeset in an approved
  typeface, so using them as-is settles this.
- **A project logo is not an acknowledgement**: a GuardIAS or OneSTOP logo does
  not signal EU support and cannot replace the emblem.
- **Accessibility**: keep the `alt` text on the image, so the statement is real
  text for screen readers and search engines.

## Where the emblem files live

The three official emblem files ship with the application and are served as
static files, so `/static/eu-funding/eu-funded-<lang>.png` resolves on any
instance:

| Language | URL on your instance |
|---|---|
| English | `/static/eu-funding/eu-funded-en.png` |
| French | `/static/eu-funding/eu-funded-fr.png` |
| Dutch | `/static/eu-funding/eu-funded-nl.png` |

There is a `-negative` variant of each for dark backgrounds (the footer uses
it). They are the Commission's own files, unmodified; see
[`static_global/eu-funding/PROVENANCE.md`](../static_global/eu-funding/PROVENANCE.md)
for their exact origin.
