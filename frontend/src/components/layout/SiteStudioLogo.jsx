import React from "react";

export function SiteStudioLogoIcon({ className = "w-8 h-8", style }) {
  return (
    <svg
      viewBox="0 0 36 36"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      style={style}
    >
      <defs>
        <linearGradient id="ss-neon-grad-1" x1="6" y1="30" x2="28" y2="6" gradientUnits="userSpaceOnUse">
          <stop stopColor="#c89666" />
          <stop offset="0.5" stopColor="#dfb180" />
          <stop offset="1" stopColor="#f4ecdf" />
        </linearGradient>
        <linearGradient id="ss-neon-grad-2" x1="12" y1="34" x2="32" y2="10" gradientUnits="userSpaceOnUse">
          <stop stopColor="#b5804f" />
          <stop offset="0.5" stopColor="#d4a373" />
          <stop offset="1" stopColor="#faedcd" />
        </linearGradient>
      </defs>
      {/* Primary dynamic angled ribbon */}
      <path
        d="M23.8 4.2C25.4 2.6 28 2.6 29.6 4.2C31.2 5.8 31.2 8.4 29.6 10L14.4 25.2C12.8 26.8 10.2 26.8 8.6 25.2C7 23.6 7 21 8.6 19.4L23.8 4.2Z"
        fill="url(#ss-neon-grad-1)"
      />
      {/* Secondary parallel dynamic ribbon with offset */}
      <path
        d="M19.2 12.8C20.8 11.2 23.4 11.2 25 12.8C26.6 14.4 26.6 17 25 18.6L13.8 29.8C12.2 31.4 9.6 31.4 8 29.8C6.4 28.2 6.4 25.6 8 24L19.2 12.8Z"
        fill="url(#ss-neon-grad-2)"
        opacity="0.92"
      />
    </svg>
  );
}

export default function SiteStudioLogo({ className = "" }) {
  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <SiteStudioLogoIcon className="w-8 h-8 flex-shrink-0" />
      <span className="font-bold text-lg tracking-tight text-white">
        Site Studio
      </span>
    </div>
  );
}

