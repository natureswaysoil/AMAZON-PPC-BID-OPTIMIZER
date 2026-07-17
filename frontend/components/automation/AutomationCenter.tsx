"use client";

import { useState } from "react";
import Link from "next/link";
import TemplatesTab from "./TemplatesTab";
import StackingRulesTab from "./StackingRulesTab";
import PreviewTab from "./PreviewTab";

type AutomationTab = "templates" | "rules" | "preview";

const TAB_LABELS: Record<AutomationTab, string> = {
  templates: "Campaign Templates",
  rules: "Stacking Rules",
  preview: "Preview / What-If",
};

export default function AutomationCenter() {
  const [tab, setTab] = useState<AutomationTab>("templates");

  return (
    <div className="min-h-screen bg-nws-bg text-nws-text">
      <header className="px-9 py-[22px] border-b border-nws-border flex items-center justify-between gap-4 flex-wrap bg-nws-surface">
        <div>
          <Link href="/" className="text-nws-accent hover:text-nws-accent2 text-xs font-mono">
            &larr; Back to Dashboard
          </Link>
          <div className="font-display text-xl font-extrabold text-nws-accent mt-1">
            Automation Center
          </div>
          <div className="text-nws-muted text-xs mt-0.5">
            ACOS-tier launch templates, stackable bid rules, and what-if previews.
          </div>
        </div>
      </header>

      <div className="px-9 border-b border-nws-border bg-nws-surface flex">
        {(Object.keys(TAB_LABELS) as AutomationTab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-5 py-3 text-xs font-mono font-medium border-b-2 transition ${
              tab === t
                ? "border-nws-accent text-nws-accent"
                : "border-transparent text-nws-muted hover:text-nws-text"
            }`}
          >
            {TAB_LABELS[t]}
          </button>
        ))}
      </div>

      <main className="p-9 max-w-5xl mx-auto">
        {tab === "templates" && <TemplatesTab />}
        {tab === "rules" && <StackingRulesTab />}
        {tab === "preview" && <PreviewTab />}
      </main>
    </div>
  );
}
