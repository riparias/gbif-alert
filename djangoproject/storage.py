"""Vite-aware staticfiles storage.

Vite chunk filenames are already content-hashed
(e.g. ``main-DKfJ6FEf.js``). Re-hashing them through Django's
``ManifestStaticFilesStorage`` breaks browser ESM loading: the
modulepreload tags Django emits get the manifest-hashed URLs, but
the static imports baked into the bundles still reference the
single-hashed (vite-hashed) URLs. Browsers treat these as separate
module records, instantiating two copies of vendor-vue /
vendor-primevue and crashing inside PrimeVue's mount.

This storage skips the manifest hashing pass for everything under
``vite/``. WhiteNoise's compression and the manifest-based serving
of non-vite static files still work as usual.
"""

from whitenoise.storage import CompressedManifestStaticFilesStorage  # type: ignore[import]


class ViteAwareStaticStorage(CompressedManifestStaticFilesStorage):
    """``CompressedManifestStaticFilesStorage`` that leaves vite chunks alone."""

    def hashed_name(self, name, content=None, filename=None):
        if name.startswith("vite/"):
            return name
        return super().hashed_name(name, content, filename)
