import React, { useState, useEffect } from "react";
import { LanguageContext } from "./LanguageContextInstance";
import { en } from "../utils/i18n/en";
import { ta } from "../utils/i18n/ta";

const translations = { en, ta };
const STORAGE_KEY = "civiclens_language";

export function LanguageProvider({ children }) {
  const [language, setLanguageState] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved === "ta" || saved === "en") {
        return saved;
      }
    } catch {
      // Fallback if localStorage unavailable
    }
    return "en";
  });

  const setLanguage = (newLang) => {
    if (newLang === "en" || newLang === "ta") {
      setLanguageState(newLang);
      try {
        localStorage.setItem(STORAGE_KEY, newLang);
      } catch {
        // Ignore storage errors
      }
    }
  };

  useEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.setAttribute("lang", language);
  }, [language]);

  // Safe nested translation lookup
  const t = (key) => {
    if (!key) return "";
    const keys = key.split(".");
    
    // Look up in active language
    let current = translations[language];
    for (const k of keys) {
      if (current && typeof current === "object" && k in current) {
        current = current[k];
      } else {
        current = null;
        break;
      }
    }

    if (current && typeof current === "string") {
      return current;
    }

    // Fallback to English
    let fallback = translations.en;
    for (const k of keys) {
      if (fallback && typeof fallback === "object" && k in fallback) {
        fallback = fallback[k];
      } else {
        fallback = null;
        break;
      }
    }

    if (fallback && typeof fallback === "string") {
      return fallback;
    }

    return key;
  };

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
}
