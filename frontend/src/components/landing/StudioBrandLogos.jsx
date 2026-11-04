import React from "react";

export function GoogleLogo({ className = "h-5 opacity-70 hover:opacity-100 transition-opacity" }) {
  return (
    <div className={`flex items-center gap-1.5 ${className}`}>
      <svg className="w-4 h-4" viewBox="0 0 24 24">
        <path
          fill="#4285F4"
          d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
        />
        <path
          fill="#34A853"
          d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
        />
        <path
          fill="#FBBC05"
          d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
        />
        <path
          fill="#EA4335"
          d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
        />
      </svg>
      <span className="font-semibold text-sm tracking-tight text-slate-200">Google</span>
    </div>
  );
}

export function MicrosoftLogo({ className = "h-5 opacity-70 hover:opacity-100 transition-opacity" }) {
  return (
    <div className={`flex items-center gap-1.5 ${className}`}>
      <svg className="w-3.5 h-3.5" viewBox="0 0 21 21">
        <rect x="1" y="1" width="9" height="9" fill="#f25022" />
        <rect x="11" y="1" width="9" height="9" fill="#7fba00" />
        <rect x="1" y="11" width="9" height="9" fill="#00a4ef" />
        <rect x="11" y="11" width="9" height="9" fill="#ffb900" />
      </svg>
      <span className="font-semibold text-sm tracking-tight text-slate-200">Microsoft</span>
    </div>
  );
}

export function MetaLogo({ className = "h-5 opacity-70 hover:opacity-100 transition-opacity" }) {
  return (
    <div className={`flex items-center gap-1.5 ${className}`}>
      <svg className="w-4 h-4 text-[#0081FB]" fill="currentColor" viewBox="0 0 24 24">
        <path d="M12 15.5c-1.5 0-2.8-1.1-3.3-2.6-.4-1.2-.2-2.5.6-3.4.8-.9 2-1.4 3.2-1.4 1.2 0 2.4.5 3.2 1.4.8.9 1 2.2.6 3.4-.5 1.5-1.8 2.6-3.3 2.6zm6.7-9.5C16.8 4.2 14.5 3 12 3S7.2 4.2 5.3 6C2 9.1 2 14.9 5.3 18c1.9 1.8 4.2 3 6.7 3s4.8-1.2 6.7-3c3.3-3.1 3.3-8.9 0-12zm-3.2 9.3c-1 1-2.2 1.5-3.5 1.5s-2.5-.5-3.5-1.5c-1-1-1.5-2.2-1.5-3.5s.5-2.5 1.5-3.5c1-1 2.2-1.5 3.5-1.5s2.5.5 3.5 1.5c1 1 1.5 2.2 1.5 3.5s-.5 2.5-1.5 3.5z" />
      </svg>
      <span className="font-semibold text-sm tracking-tight text-slate-200">Meta</span>
    </div>
  );
}

export function NotionLogo({ className = "h-5 opacity-70 hover:opacity-100 transition-opacity" }) {
  return (
    <div className={`flex items-center gap-1.5 ${className}`}>
      <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
        <path d="M4.459 4.208c.746.606 1.026.56 2.428.466l13.215-.793c.28 0 .047-.28-.046-.326L17.86 1.69c-.466-.373-.84-.513-1.68-.42l-10.824.746c-.513.047-.653.28-.42.56l-.477 1.632zm.98 3.593v12.873c0 .84.373 1.12 1.213 1.073l13.822-.84c.84-.046.933-.56.933-1.212V6.914c0-.653-.28-.98-.84-.933l-14.288.84c-.653.047-.84.373-.84.98zm12.603.653c.093.42 0 .84-.42.887l-.98.14v8.583c-.467.28-.934.42-1.4.42-.747 0-1.074-.233-1.633-.933l-4.152-6.577v6.623l1.4.327c.42.093.373.606.373.606l-3.36.233c-.093-.373 0-.793.42-.886l1.026-.234V8.734l-1.353-.14c-.42-.047-.373-.56-.373-.56l3.407-.234 4.526 6.95v-6.3l-1.167-.14c-.42-.046-.373-.56-.373-.56l3.69-.233z" />
      </svg>
      <span className="font-semibold text-sm tracking-tight text-slate-200">Notion</span>
    </div>
  );
}

export function FigmaLogo({ className = "h-5 opacity-70 hover:opacity-100 transition-opacity" }) {
  return (
    <div className={`flex items-center gap-1.5 ${className}`}>
      <svg className="w-3.5 h-3.5" viewBox="0 0 38 57" fill="none">
        <path d="M19 28.5C19 23.2533 23.2533 19 28.5 19C33.7467 19 38 23.2533 38 28.5C38 33.7467 33.7467 38 28.5 38C23.2533 38 19 33.7467 19 28.5Z" fill="#1ABCFE" />
        <path d="M0 47.5C0 42.2533 4.25329 38 9.5 38H19V47.5C19 52.7467 14.7467 57 9.5 57C4.25329 57 0 52.7467 0 47.5Z" fill="#0ACF83" />
        <path d="M19 0V19H28.5C33.7467 19 38 14.7467 38 9.5C38 4.25329 33.7467 0 28.5 0H19Z" fill="#FF7262" />
        <path d="M0 9.5C0 14.7467 4.25329 19 9.5 19H19V0H9.5C4.25329 0 0 4.25329 0 9.5Z" fill="#F24E1E" />
        <path d="M0 28.5C0 33.7467 4.25329 38 9.5 38H19V19H9.5C4.25329 19 0 23.2533 0 28.5Z" fill="#A259FF" />
      </svg>
      <span className="font-semibold text-sm tracking-tight text-slate-200">Figma</span>
    </div>
  );
}

export function MouseCursorPointer({ className = "w-6 h-6" }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      style={{ filter: "drop-shadow(0 4px 8px rgba(0,0,0,0.6))" }}
    >
      <path
        d="M5.5 3.5L18.5 12L12.5 13.5L16 20.5L13.5 21.5L10 14.5L5.5 18.5V3.5Z"
        fill="#FFFFFF"
        stroke="#1E293B"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
    </svg>
  );
}

