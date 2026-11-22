import React from "react";
import { Languages } from "lucide-react";
import { useLanguage } from "../../hooks/useLanguage";

export function LanguageSwitcher({ variant = "toggle", className = "" }) {
  const { language, setLanguage } = useLanguage();

  if (variant === "compact") {
    return (
      <button
        type="button"
        onClick={() => setLanguage(language === "en" ? "ta" : "en")}
        className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-xs font-semibold text-slate-700 shadow-2xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 ${className}`}
        aria-label="Switch Language"
        title={language === "en" ? "தமிழுக்கு மாற்றவும்" : "Switch to English"}
      >
        <Languages className="w-3.5 h-3.5 text-blue-700" />
        <span>{language === "en" ? "தமிழ்" : "English"}</span>
      </button>
    );
  }

  return (
    <div
      role="group"
      aria-label="Language selection"
      className={`inline-flex items-center p-0.5 rounded-lg border border-slate-200 bg-slate-100 shadow-2xs ${className}`}
    >
      <button
        type="button"
        onClick={() => setLanguage("en")}
        aria-pressed={language === "en"}
        className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 ${
          language === "en"
            ? "bg-white text-blue-800 shadow-xs"
            : "text-slate-600 hover:text-slate-900"
        }`}
      >
        English
      </button>
      <button
        type="button"
        onClick={() => setLanguage("ta")}
        aria-pressed={language === "ta"}
        className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 ${
          language === "ta"
            ? "bg-white text-blue-800 shadow-xs"
            : "text-slate-600 hover:text-slate-900"
        }`}
      >
        தமிழ்
      </button>
    </div>
  );
}
