import React from "react";

export function Spinner({ size = "md", className = "", color = "currentColor" }) {
  const sizeClasses = {
    sm: "w-4 h-4 border-2",
    md: "w-5 h-5 border-2",
    lg: "w-8 h-8 border-3",
  };

  return (
    <div
      role="status"
      aria-label="Loading"
      className={`inline-block animate-spin rounded-full border-t-transparent ${sizeClasses[size] || sizeClasses.md} ${className}`}
      style={{ borderColor: color, borderTopColor: "transparent" }}
    >
      <span className="sr-only">Loading...</span>
    </div>
  );
}
