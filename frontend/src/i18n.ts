import en from './locales/en.json';

export type TranslationKey = keyof typeof en;

const translations: Record<string, Record<string, string>> = {
  en,
};

export const DEFAULT_LOCALE = 'en';

export function t(key: TranslationKey, locale: string = DEFAULT_LOCALE): string {
  const dictionary = translations[locale] ?? translations[DEFAULT_LOCALE];
  return dictionary[key] ?? key;
}

