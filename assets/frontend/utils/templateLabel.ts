// Picks the language-specific string for an AlertTemplateOut field group,
// mirroring utils/vernacular.ts. `locale` is the vue-i18n locale ref value.
export function pickByLocale(
  en: string,
  fr: string,
  nl: string,
  locale: string,
): string {
  const code = locale.slice(0, 2);
  if (code === "nl") return nl;
  if (code === "fr") return fr;
  return en;
}
