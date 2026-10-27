// Picks the active locale's text from an AlertTemplateOut per-language field
// (names, descriptions). `locale` is the vue-i18n locale ref value. Falls back to
// English, the language every template is written in, so a card is never untitled.
export function pickByLocale(byLanguage: Record<string, string>, locale: string): string {
    return byLanguage[locale.slice(0, 2)] || byLanguage.en || "";
}
