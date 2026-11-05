"""Populate Species.vernacular_name_<lang> from the Catalogue of Life.

Names come from COL XR via ChecklistBank, looked up by gbif_col_taxon_key, for
each language in GBIF_ALERT["ENABLED_LANGUAGES"]. By default only blank names
are filled; --overwrite also replaces existing ones. A language the source has
no name for is never blanked.
"""
import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from modeltranslation.utils import build_localized_fieldname  # type: ignore

from dashboard.models import Species
from dashboard.species_images import USER_AGENT

# "3LXR" is ChecklistBank's alias for the latest COL XR release - the checklist
# behind settings.GBIF_COL_XR_CHECKLIST_KEY, whose taxon ids it shares.
_VERNACULAR_URL = "https://api.checklistbank.org/dataset/3LXR/taxon/{key}/vernacular"
_TIMEOUT = 15

# Our language codes (ISO 639-1) -> the ISO 639-3 codes the source uses. COL
# tags most Norwegian names with the generic "nor", so Bokmal accepts both.
LANGUAGE_CODES = {
    "en": ("eng",),
    "fr": ("fra",),
    "nl": ("nld",),
    "nb": ("nob", "nor"),
    "pt": ("por",),
}

_MAX_LENGTH: int = Species._meta.get_field("vernacular_name").max_length  # type: ignore[assignment]


def fetch_vernacular_names(col_taxon_key: str) -> list[dict]:
    """Return ChecklistBank's vernacular name entries for a COL XR taxon key.

    An unknown key yields an empty list, not an error.
    """
    resp = requests.get(
        _VERNACULAR_URL.format(key=col_taxon_key),
        headers={"User-Agent": USER_AGENT},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def pick_name(entries: list[dict], codes: tuple[str, ...]) -> str | None:
    """Pick one name among the entries in the given languages.

    A name flagged preferred wins; otherwise the first one, in source order.
    Names too long for the column are skipped rather than truncated.
    """
    candidates = [
        e["name"]
        for e in sorted(entries, key=lambda e: not e.get("preferred"))
        if e.get("language") in codes and len(e.get("name", "")) <= _MAX_LENGTH
    ]
    return candidates[0] if candidates else None


class Command(BaseCommand):
    help = "Populate Species vernacular names from the Catalogue of Life."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Also replace existing names, including ones typed in the admin.",
        )

    def handle(self, *args, **options):
        languages = []
        for lang in settings.GBIF_ALERT["ENABLED_LANGUAGES"]:
            if lang in LANGUAGE_CODES:
                languages.append(lang)
            else:
                self.stderr.write(f"No ISO 639-3 code known for {lang!r}, skipped")

        updated = 0
        for species in Species.objects.exclude(gbif_col_taxon_key=None):
            # One bad species (network error, odd response) must not abort the run.
            try:
                entries = fetch_vernacular_names(species.gbif_col_taxon_key)
                changed = []
                for lang in languages:
                    field = build_localized_fieldname("vernacular_name", lang)
                    if getattr(species, field) and not options["overwrite"]:
                        continue
                    name = pick_name(entries, LANGUAGE_CODES[lang])
                    if name is None or name == getattr(species, field):
                        continue
                    self.stdout.write(f"  {species.name} [{lang}] <- {name}")
                    setattr(species, field, name)
                    changed.append(field)
                if changed:
                    if not options["dry_run"]:
                        species.save(update_fields=changed)
                    updated += 1
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(f"  skipped {species.name}: {exc}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {updated} species updated"
                + (" (dry-run, nothing written)" if options["dry_run"] else "")
            )
        )
