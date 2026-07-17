"use client";

import { useState } from "react";
import { card, btnPrimary, input, label as labelClass } from "./ui";

interface PreviewSummary {
  dry_run: boolean;
  message: string;
  keywords_evaluated: number;
  keywords_with_projected_changes: number;
  keywords_projected_to_increase: number;
  keywords_projected_to_decrease: number;
  keywords_projected_to_pause: number;
  current_bid_total: number;
  projected_bid_total: number;
  projected_bid_delta: number;
  sample_changes: Array<{
    keyword_id: string;
    keyword_text: string;
    campaign_id: string;
    current_bid: number;
    new_bid: number;
    pause_recommended: boolean;
    reasoning: string;
  }>;
  error?: boolean;
  message_error?: string;
}

export default function PreviewTab() {
  const [targetAcos, setTargetAcos] = useState("");
  const [rulesJson, setRulesJson] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PreviewSummary | null>(null);
  const [error, setError] = useState("");

  const runPreview = async () => {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const body: Record<string, any> = {};
      if (targetAcos.trim() !== "") {
        body.target_acos = Number(targetAcos) / 100;
      }
      if (rulesJson.trim() !== "") {
        try {
          body.rules = JSON.parse(rulesJson);
        } catch {
          setError("Rules must be valid JSON, e.g. [{\"type\":\"spend_cap_pause\",\"enabled\":true,\"params\":{\"max_cost_30d\":25}}]");
          setLoading(false);
          return;
        }
      }

      const res = await fetch("/api/preview-optimization", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok || data.error) {
        setError(data.message || "Preview failed");
      } else {
        setResult(data);
      }
    } catch {
      setError("Failed to reach the preview service");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <p className="text-sm text-nws-muted">
        Test a hypothetical target ACOS and/or stacking rule set against recent data and see projected bid
        changes - nothing here ever writes to BigQuery or calls the Amazon Ads API. Run this any time, not
        only during initial onboarding.
      </p>

      {error && (
        <div className="p-3 bg-nws-danger/10 border border-nws-danger rounded-card text-nws-danger text-sm">
          {error}
        </div>
      )}

      <div className={card}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Hypothetical Target ACOS (%, optional)</label>
            <input
              className={input}
              type="number"
              step="1"
              placeholder="Leave blank to use the live target"
              value={targetAcos}
              onChange={(e) => setTargetAcos(e.target.value)}
            />
          </div>
        </div>

        <div className="mt-4">
          <label className={labelClass}>Hypothetical Stacking Rules (JSON list, optional)</label>
          <textarea
            className={`${input} font-mono text-xs`}
            rows={3}
            placeholder='[{"type":"spend_cap_pause","enabled":true,"params":{"max_cost_30d":25}}]'
            value={rulesJson}
            onChange={(e) => setRulesJson(e.target.value)}
          />
          <p className="text-xs text-nws-muted mt-1">
            Leave blank to use each campaign&apos;s saved rule set (see the Stacking Rules tab).
          </p>
        </div>

        <button className={`${btnPrimary} mt-4`} onClick={runPreview} disabled={loading}>
          {loading ? "Running preview..." : "Run Preview"}
        </button>
      </div>

      {result && (
        <div className={card}>
          <h3 className="font-display text-lg font-bold text-nws-accent mb-4">Projected Impact</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <Stat label="Evaluated" value={result.keywords_evaluated} />
            <Stat label="Would Change" value={result.keywords_with_projected_changes} />
            <Stat label="Would Increase" value={result.keywords_projected_to_increase} />
            <Stat label="Would Decrease" value={result.keywords_projected_to_decrease} />
            <Stat label="Would Pause" value={result.keywords_projected_to_pause} />
            <Stat label="Current Bid Total" value={`$${result.current_bid_total.toFixed(2)}`} />
            <Stat label="Projected Bid Total" value={`$${result.projected_bid_total.toFixed(2)}`} />
            <Stat
              label="Projected Delta"
              value={`${result.projected_bid_delta >= 0 ? "+" : ""}$${result.projected_bid_delta.toFixed(2)}`}
              accent={result.projected_bid_delta > 0 ? "danger" : result.projected_bid_delta < 0 ? "accent" : undefined}
            />
          </div>

          {result.sample_changes.length > 0 && (
            <div>
              <div className="text-xs font-medium text-nws-muted mb-2">Largest projected changes</div>
              <div className="space-y-2">
                {result.sample_changes.map((c) => (
                  <div key={c.keyword_id} className="p-3 bg-nws-bg border border-nws-border rounded-[7px]">
                    <div className="flex justify-between text-sm">
                      <span className="text-nws-text">{c.keyword_text}</span>
                      <span className={c.pause_recommended ? "text-nws-danger" : "text-nws-accent"}>
                        ${c.current_bid.toFixed(2)} &rarr; ${c.new_bid.toFixed(2)}
                        {c.pause_recommended ? " (pause)" : ""}
                      </span>
                    </div>
                    <div className="text-xs text-nws-muted mt-1">{c.reasoning}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string | number; accent?: "accent" | "danger" }) {
  const color = accent === "accent" ? "text-nws-accent" : accent === "danger" ? "text-nws-danger" : "text-nws-text";
  return (
    <div>
      <div className="text-xs text-nws-muted">{label}</div>
      <div className={`text-lg font-bold ${color}`}>{value}</div>
    </div>
  );
}
