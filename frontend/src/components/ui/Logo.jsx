import React from "react";
import { Link } from "react-router-dom";
import { ShieldCheck } from "lucide-react";

export function Logo({
  showTagline = false,
  size = "md",
  to = "/",
  className = "",
}) {
  const sizeMap = {
    sm: {
      icon: "w-5 h-5",
      container: "w-7 h-7 rounded-lg",
      text: "text-lg",
    },
    md: {
      icon: "w-6 h-6",
      container: "w-9 h-9 rounded-xl",
      text: "text-xl",
    },
    lg: {
      icon: "w-8 h-8",
      container: "w-11 h-11 rounded-2xl",
      text: "text-2xl",
    },
  };

  const current = sizeMap[size] || sizeMap.md;

  const content = (
    <div className={`flex items-center gap-2.5 select-none ${className}`}>
      <div
        className={`${current.container} bg-gradient-to-br from-blue-700 to-blue-900 text-white flex items-center justify-center shadow-xs flex-shrink-0 ring-1 ring-blue-800/20`}
      >
        <ShieldCheck className={current.icon} />
      </div>
      <div className="flex flex-col">
        <span className={`font-bold tracking-tight text-slate-900 ${current.text} flex items-center`}>
          Civic<span className="text-blue-700">Lens</span>
          <span className="ml-1.5 inline-block w-1.5 h-1.5 rounded-full bg-teal-500" />
        </span>
        {showTagline && (
          <span className="text-[10px] uppercase tracking-wider font-semibold text-slate-500">
            Understand. Verify. Act.
          </span>
        )}
      </div>
    </div>
  );

  if (to) {
    return (
      <Link
        to={to}
        className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 rounded-lg"
      >
        {content}
      </Link>
    );
  }

  return content;
}
