import React from "react";

export function Skeleton({
  className = "",
  width,
  height,
  rounded = "rounded-md",
  ...props
}) {
  return (
    <div
      aria-hidden="true"
      className={`animate-pulse bg-slate-200 ${rounded} ${className}`}
      style={{
        width: width !== undefined ? width : undefined,
        height: height !== undefined ? height : undefined,
      }}
      {...props}
    />
  );
}
