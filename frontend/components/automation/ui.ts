// Shared style tokens for the automation-center tabs, matching
// ControlPanel.tsx's nws-* design system (see tailwind.config.js).
export const card = "bg-nws-surface border border-nws-border rounded-card p-6";
export const btnBase =
  "font-mono text-[11px] font-medium px-[15px] py-2 rounded-[7px] border cursor-pointer transition inline-flex items-center gap-1.5 whitespace-nowrap disabled:opacity-35 disabled:cursor-not-allowed";
export const btnGhost = `${btnBase} bg-transparent border-nws-border text-nws-muted hover:border-nws-accent hover:text-nws-accent`;
export const btnPrimary = `${btnBase} bg-nws-accent border-nws-accent text-nws-bg font-bold hover:bg-nws-accent2 hover:border-nws-accent2`;
export const btnWarn = `${btnBase} bg-transparent border-nws-warn text-nws-warn hover:bg-nws-warn/10`;
export const btnDanger = `${btnBase} bg-transparent border-nws-danger text-nws-danger hover:bg-nws-danger/10`;
export const btnAccent = `${btnBase} bg-transparent border-nws-accent text-nws-accent hover:bg-nws-accent/10`;
export const input =
  "w-full px-3 py-2 bg-nws-bg border border-nws-border rounded-[7px] text-nws-text placeholder-nws-muted focus:outline-none focus:border-nws-accent font-mono text-sm";
export const label = "block text-xs font-medium text-nws-muted mb-1.5";
