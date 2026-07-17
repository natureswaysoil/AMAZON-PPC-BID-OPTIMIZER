"use client";

import { useEffect, useState } from "react";
import { card, btnPrimary, btnAccent, label as labelClass } from "./ui";

interface Product {
  sku: string;
  asin: string;
  product_name: string;
}

interface TemplateConfig {
  label: string;
  target_acos: number;
  budget: number;
  fallback_bid: number;
  purpose: string;
}

interface PreviewCampaign {
  name: string;
  type: string;
  daily_budget: number;
  starting_bid?: number;
  purpose: string;
  keywords?: Array<{ keyword: string }>;
}

interface PreviewResult {
  dry_run: boolean;
  message: string;
  product: { title: string; asin: string; sku: string };
  settings: {
    daily_budget_total: number;
    fallback_bid: number;
    template: string | null;
    template_label: string | null;
    template_purpose: string | null;
    target_acos: number | null;
  };
  campaigns: PreviewCampaign[];
  review_checklist: string[];
  confirm_required?: boolean;
  error?: string;
}

export default function TemplatesTab() {
  const [products, setProducts] = useState<Product[]>([]);
  const [templates, setTemplates] = useState<Record<string, TemplateConfig>>({});
  const [selectedAsin, setSelectedAsin] = useState("");
  const [selectedTemplate, setSelectedTemplate] = useState("");
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [launching, setLaunching] = useState(false);
  const [launchResult, setLaunchResult] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/campaigns/products")
      .then((r) => r.json())
      .then((data) => setProducts(data.products || []))
      .catch(() => setProducts([]));

    fetch("/api/campaign-templates")
      .then((r) => r.json())
      .then((data) => setTemplates(data.templates || {}))
      .catch(() => setTemplates({}));
  }, []);

  const selectedProduct = products.find((p) => p.asin === selectedAsin);

  const runPreview = async () => {
    if (!selectedProduct || !selectedTemplate) return;
    setLoading(true);
    setError("");
    setPreview(null);
    setLaunchResult(null);
    try {
      const res = await fetch("/api/campaign-templates/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          product: { asin: selectedProduct.asin, sku: selectedProduct.sku, title: selectedProduct.product_name },
          template: selectedTemplate,
        }),
      });
      const data = await res.json();
      if (!res.ok || data.error) {
        setError(data.error || data.message || "Failed to build preview");
      } else {
        setPreview(data);
      }
    } catch {
      setError("Failed to reach the preview service");
    } finally {
      setLoading(false);
    }
  };

  const confirmLaunch = async () => {
    if (!selectedProduct || !selectedTemplate) return;
    setLaunching(true);
    setError("");
    try {
      const res = await fetch("/api/campaign-templates/launch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          product: { asin: selectedProduct.asin, sku: selectedProduct.sku, title: selectedProduct.product_name },
          template: selectedTemplate,
        }),
      });
      const data = await res.json();
      if (!res.ok || data.error) {
        setError(data.error || data.message || "Launch failed");
      } else {
        setLaunchResult(data);
      }
    } catch {
      setError("Failed to reach the launch service");
    } finally {
      setLaunching(false);
    }
  };

  return (
    <div className="space-y-6">
      <p className="text-sm text-nws-muted">
        Pick a product, pick an ACOS-tier template, review the resolved plan, then launch in shadow mode
        (dry-run) before it ever touches real spend.
      </p>

      {error && (
        <div className="p-3 bg-nws-danger/10 border border-nws-danger rounded-card text-nws-danger text-sm">
          {error}
        </div>
      )}

      <div className={card}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Product (ASIN)</label>
            <select
              value={selectedAsin}
              onChange={(e) => {
                setSelectedAsin(e.target.value);
                setPreview(null);
                setLaunchResult(null);
              }}
              className="w-full px-3 py-2 bg-nws-bg border border-nws-border rounded-[7px] text-nws-text font-mono text-sm"
            >
              <option value="">Select a product...</option>
              {products.map((p) => (
                <option key={p.asin || p.sku} value={p.asin}>
                  {p.product_name} ({p.asin || p.sku})
                </option>
              ))}
            </select>
            {products.length === 0 && (
              <p className="text-xs text-nws-muted mt-1">No products loaded yet.</p>
            )}
          </div>

          <div>
            <label className={labelClass}>Template</label>
            <select
              value={selectedTemplate}
              onChange={(e) => {
                setSelectedTemplate(e.target.value);
                setPreview(null);
                setLaunchResult(null);
              }}
              className="w-full px-3 py-2 bg-nws-bg border border-nws-border rounded-[7px] text-nws-text font-mono text-sm"
            >
              <option value="">Select a template...</option>
              {Object.entries(templates).map(([key, t]) => (
                <option key={key} value={key}>
                  {t.label} (target ACOS {(t.target_acos * 100).toFixed(0)}%)
                </option>
              ))}
            </select>
          </div>
        </div>

        {selectedTemplate && templates[selectedTemplate] && (
          <p className="text-xs text-nws-muted mt-3">{templates[selectedTemplate].purpose}</p>
        )}

        <button
          className={`${btnPrimary} mt-4`}
          disabled={!selectedProduct || !selectedTemplate || loading}
          onClick={runPreview}
        >
          {loading ? "Building preview..." : "Preview Plan"}
        </button>
      </div>

      {preview && (
        <div className={card}>
          <h3 className="font-display text-lg font-bold text-nws-accent mb-1">
            {preview.settings.template_label} plan for {preview.product.title}
          </h3>
          <p className="text-xs text-nws-muted mb-4">{preview.settings.template_purpose}</p>

          <div className="grid grid-cols-3 gap-4 mb-4">
            <div>
              <div className="text-xs text-nws-muted">Target ACOS</div>
              <div className="text-lg font-bold text-nws-accent">
                {preview.settings.target_acos != null ? `${(preview.settings.target_acos * 100).toFixed(0)}%` : "—"}
              </div>
            </div>
            <div>
              <div className="text-xs text-nws-muted">Daily Budget</div>
              <div className="text-lg font-bold text-nws-text">${preview.settings.daily_budget_total.toFixed(2)}</div>
            </div>
            <div>
              <div className="text-xs text-nws-muted">Fallback Bid</div>
              <div className="text-lg font-bold text-nws-text">${preview.settings.fallback_bid.toFixed(2)}</div>
            </div>
          </div>

          <div className="space-y-2 mb-4">
            {preview.campaigns.map((c, i) => (
              <div key={i} className="p-3 bg-nws-bg border border-nws-border rounded-[7px]">
                <div className="text-sm font-medium text-nws-text">{c.name}</div>
                <div className="text-xs text-nws-muted mt-1">
                  ${c.daily_budget.toFixed(2)}/day
                  {c.starting_bid != null ? ` · starting bid $${c.starting_bid.toFixed(2)}` : ""}
                  {c.keywords ? ` · ${c.keywords.length} keywords` : ""}
                </div>
                <div className="text-xs text-nws-muted">{c.purpose}</div>
              </div>
            ))}
          </div>

          <div className="mb-4">
            <div className="text-xs font-medium text-nws-muted mb-1">Review checklist</div>
            <ul className="text-xs text-nws-muted list-disc list-inside space-y-1">
              {preview.review_checklist.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </div>

          <button className={btnAccent} disabled={launching} onClick={confirmLaunch}>
            {launching ? "Launching..." : "Confirm & Launch (Shadow Mode)"}
          </button>
        </div>
      )}

      {launchResult && (
        <div className={card}>
          <h3 className="font-bold text-nws-accent mb-2">{launchResult.message || "Launch result"}</h3>
          <pre className="text-xs text-nws-muted overflow-auto bg-nws-bg p-4 rounded-[7px] max-h-96">
            {JSON.stringify(launchResult, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
