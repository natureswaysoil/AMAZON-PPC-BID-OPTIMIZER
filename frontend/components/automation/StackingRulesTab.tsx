"use client";

import { useEffect, useState } from "react";
import { card, btnGhost, btnPrimary, input, label as labelClass } from "./ui";

interface ParamSchema {
  label: string;
  type: "number" | "hour_ranges";
  default: any;
}

interface RuleTypeMeta {
  label: string;
  description: string;
  params: Record<string, ParamSchema>;
}

interface RuleConfig {
  type: string;
  enabled: boolean;
  params: Record<string, any>;
}

function paramsToText(params: Record<string, any>): string {
  return JSON.stringify(params ?? {});
}

export default function StackingRulesTab() {
  const [types, setTypes] = useState<Record<string, RuleTypeMeta>>({});
  const [scope, setScope] = useState("default");
  const [rules, setRules] = useState<RuleConfig[]>([]);
  const [paramsText, setParamsText] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/stacking-rules/types")
      .then((r) => r.json())
      .then((data) => setTypes(data.types || {}))
      .catch(() => setTypes({}));
  }, []);

  const loadRules = async (targetScope: string) => {
    setLoading(true);
    setError("");
    setMessage("");
    try {
      const res = await fetch(`/api/stacking-rules?scope=${encodeURIComponent(targetScope)}`);
      const data = await res.json();
      if (!res.ok || data.error) {
        setError(data.error || "Failed to load rules");
        return;
      }
      const savedByType = new Map<string, RuleConfig>((data.rules || []).map((r: RuleConfig) => [r.type, r]));
      const merged = Object.keys(types).length
        ? Object.keys(types).map(
            (type) => savedByType.get(type) || { type, enabled: false, params: defaultParams(type) }
          )
        : data.rules || [];
      setRules(merged);
      setParamsText(Object.fromEntries(merged.map((r: RuleConfig) => [r.type, paramsToText(r.params)])));
    } catch {
      setError("Failed to reach the stacking-rules service");
    } finally {
      setLoading(false);
    }
  };

  function defaultParams(type: string): Record<string, any> {
    const meta = types[type];
    if (!meta) return {};
    return Object.fromEntries(Object.entries(meta.params).map(([k, v]) => [k, v.default]));
  }

  useEffect(() => {
    if (Object.keys(types).length > 0) {
      loadRules(scope);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [types]);

  const toggleEnabled = (type: string, enabled: boolean) => {
    setRules((prev) => prev.map((r) => (r.type === type ? { ...r, enabled } : r)));
  };

  const updateParamsText = (type: string, text: string) => {
    setParamsText((prev) => ({ ...prev, [type]: text }));
  };

  const save = async () => {
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const finalRules = rules.map((r) => {
        let params = r.params;
        try {
          params = JSON.parse(paramsText[r.type] ?? "{}");
        } catch {
          throw new Error(`Invalid JSON in params for ${r.type}`);
        }
        return { type: r.type, enabled: r.enabled, params };
      });

      const res = await fetch("/api/stacking-rules", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scope, rules: finalRules }),
      });
      const data = await res.json();
      if (!res.ok || data.error) {
        setError(data.error || data.message || "Failed to save rules");
      } else {
        setMessage(`Saved rules for scope "${scope}".`);
        setRules(finalRules);
      }
    } catch (e: any) {
      setError(e.message || "Failed to save rules");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <p className="text-sm text-nws-muted">
        Stack any of the {Object.keys(types).length || 4} rule types on top of the ACOS-tier bid decision.
        Everything is off by default - enabling a rule here is what makes it apply on the next bid-optimizer run.
      </p>

      {error && (
        <div className="p-3 bg-nws-danger/10 border border-nws-danger rounded-card text-nws-danger text-sm">
          {error}
        </div>
      )}
      {message && (
        <div className="p-3 bg-nws-accent/10 border border-nws-accent rounded-card text-nws-accent text-sm">
          {message}
        </div>
      )}

      <div className={card}>
        <label className={labelClass}>Scope</label>
        <div className="flex gap-2 items-center">
          <input
            className={input}
            value={scope}
            onChange={(e) => setScope(e.target.value)}
            placeholder="default or a campaign_id"
          />
          <button className={btnGhost} onClick={() => loadRules(scope)} disabled={loading}>
            {loading ? "Loading..." : "Load"}
          </button>
        </div>
        <p className="text-xs text-nws-muted mt-1">
          Use &quot;default&quot; for the account-wide rule set, or a specific campaign_id to override it for
          just that campaign.
        </p>
      </div>

      {rules.map((rule) => {
        const meta = types[rule.type];
        return (
          <div key={rule.type} className={card}>
            <div className="flex items-center justify-between mb-2">
              <div>
                <div className="font-medium text-nws-text">{meta?.label || rule.type}</div>
                <div className="text-xs text-nws-muted">{meta?.description}</div>
              </div>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={rule.enabled}
                  onChange={(e) => toggleEnabled(rule.type, e.target.checked)}
                  className="w-4 h-4 accent-nws-accent"
                />
                <span className="text-xs text-nws-muted">{rule.enabled ? "Enabled" : "Disabled"}</span>
              </label>
            </div>

            {meta && (
              <div className="text-xs text-nws-muted mb-2">
                Params: {Object.entries(meta.params).map(([k, v]) => v.label).join(", ")}
              </div>
            )}

            <textarea
              className={`${input} font-mono text-xs`}
              rows={2}
              value={paramsText[rule.type] ?? "{}"}
              onChange={(e) => updateParamsText(rule.type, e.target.value)}
            />
          </div>
        );
      })}

      {rules.length > 0 && (
        <button className={btnPrimary} onClick={save} disabled={saving}>
          {saving ? "Saving..." : `Save Rules for "${scope}"`}
        </button>
      )}
    </div>
  );
}
