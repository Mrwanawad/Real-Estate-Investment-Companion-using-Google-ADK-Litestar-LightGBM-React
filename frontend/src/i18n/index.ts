import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import arEG from "./ar-EG.json";
import en from "./en.json";

export const RTL_LANGUAGES = ["ar"];

export function directionFor(language: string): "rtl" | "ltr" {
  return RTL_LANGUAGES.includes(language.split("-")[0]) ? "rtl" : "ltr";
}

void i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, "ar-EG": { translation: arEG } },
  lng: "en",
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

export default i18n;
