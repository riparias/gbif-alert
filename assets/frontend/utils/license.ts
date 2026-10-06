// Short label for a license as GBIF publishes it: Creative Commons URLs become
// "CC BY-NC 4.0" / "CC0 1.0"; anything else (free text, other URLs) is
// returned unchanged.
export function licenseLabel(license: string): string {
    const m = license.match(
        /creativecommons\.org\/(?:licenses\/([a-z-]+)|publicdomain\/(zero))\/([\d.]+)/i,
    );
    if (!m) return license;
    return m[2] ? `CC0 ${m[3]}` : `CC ${m[1].toUpperCase()} ${m[3]}`;
}
