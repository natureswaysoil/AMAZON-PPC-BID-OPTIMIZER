"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";

interface CampaignBudget {
  budget?: number;
}

interface Campaign {
  campaignId: string;
  campaignName?: string;
  name?: string;
  state?: string;
  budget?: CampaignBudget;
  spend?: number;
  sales?: number;
  impressions?: number;
  clicks?: number;
  acos?: number | null;
  amazonSuggestedBidLow?: number | null;
  amazonSuggestedBidHigh?: number | null;
  currentAppliedBid?: number | null;
  currentBidMode?: string;
}

interface Product {
  product_id: string;
  sku: string;
  asin: string;
  title: string;
  price: string;
  active: boolean;
  keywords?: string;
  research_keywords?: string;
  suggested_budget?: number;
  suggested_bid?: number;
}

interface Keyword {
  keyword_id: string;
  keyword_text: string;
  match_type: string;
  current_bid: number;
  campaign_name: string;
  clicks_30d: number;
  conversions_30d: number;
  cost_30d: number;
  sales_30d: number;
  acos: number | null;
}

type Tab = "campaigns" | "products" | "keywords";

function money(v: number | null | undefined): string {
  return "$" + Number(v || 0).toFixed(2);
}

function pct(v: number | null | undefined, digits = 1): string {
  if (v == null || isNaN(+v)) return "—";
  return (+v * 100).toFixed(digits) + "%";
}

function acosClass(v: number | null | undefined): string {
  if (v == null || isNaN(+v)) return "text-nws-text";
  return +v < 0.3 ? "text-nws-accent" : +v < 0.5 ? "text-nws-warn" : "text-nws-danger";
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

function estimateBidWindow(c: Campaign, applied: number | null | undefined) {
  const base = applied != null && isFinite(+applied) ? +applied : 0.75;
  const budget = +(c.budget?.budget ?? 25);
  const clicks = +(c.clicks ?? 0);
  const acos = c.acos != null && isFinite(+c.acos) ? +c.acos : null;

  const budgetFactor = clamp(Math.sqrt(Math.max(budget, 5) / 25), 0.8, 1.4);
  const volumeFactor = clamp(0.9 + Math.min(clicks, 200) / 1000, 0.9, 1.1);

  let perfFactor = 1.0;
  if (acos == null) perfFactor = 0.95;
  else if (acos <= 0.25) perfFactor = 1.18;
  else if (acos <= 0.35) perfFactor = 1.08;
  else if (acos <= 0.5) perfFactor = 1.0;
  else if (acos <= 0.7) perfFactor = 0.9;
  else perfFactor = 0.8;

  const center = clamp(base * budgetFactor * volumeFactor * perfFactor, 0.25, 2.5);
  return { low: +(center * 0.72).toFixed(2), high: +(center * 1.28).toFixed(2) };
}

const btnBase =
  "font-mono text-[11px] font-medium px-[15px] py-2 rounded-[7px] border cursor-pointer transition inline-flex items-center gap-1.5 whitespace-nowrap disabled:opacity-35 disabled:cursor-not-allowed";
const btnGhost = `${btnBase} bg-transparent border-nws-border text-nws-muted hover:border-nws-accent hover:text-nws-accent`;
const btnPrimary = `${btnBase} bg-nws-accent border-nws-accent text-nws-bg font-bold hover:bg-nws-accent2 hover:border-nws-accent2`;
const btnWarn = `${btnBase} bg-transparent border-nws-warn text-nws-warn hover:bg-nws-warn/10`;
const btnDanger = `${btnBase} bg-transparent border-nws-danger text-nws-danger hover:bg-nws-danger/10`;
const btnAccent = `${btnBase} bg-transparent border-nws-accent text-nws-accent hover:bg-nws-accent/10`;
const btnBlue = `${btnBase} bg-transparent border-nws-blue text-nws-blue hover:bg-nws-blue/10`;
const btnSm = "!px-[11px] !py-[5px] !text-[10px]";

export default function ControlPanel() {
  const [tab, setTab] = useState<Tab>("campaigns");
  const [dashboardData, setDashboardData] = useState<any>(null);
  const [dashboardError, setDashboardError] = useState<string | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [keywords, setKeywords] = useState<Keyword[]>([]);
  const [loading, setLoading] = useState(true);
  const [toastMsg, setToastMsg] = useState<{ msg: string; err?: boolean } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [prodSearch, setProdSearch] = useState("");
  const [diagStats, setDiagStats] = useState<any>(null);
  const [diagPlan, setDiagPlan] = useState<any>(null);

  const [launchProduct, setLaunchProduct] = useState<Product | null>(null);
  const [launchBudget, setLaunchBudget] = useState("");
  const [launchBid, setLaunchBid] = useState("");
  const [launchPreview, setLaunchPreview] = useState<{ low?: string; mid?: string; high?: string }>({});
  const [launching, setLaunching] = useState(false);

  const showToast = useCallback((msg: string, err = false) => {
    setToastMsg({ msg, err });
    setTimeout(() => setToastMsg(null), 4000);
  }, []);

  const loadDashboard = useCallback(async () => {
    try {
      const res = await fetch("/api/dashboard-data", { cache: "no-store" });
      const data = await res.json();
      if (!res.ok || data.error) throw new Error(data.error || "Dashboard data failed to load");
      setDashboardData(data);
      setDashboardError(null);
      if (data.cache_rebuild_in_progress) {
        setTimeout(loadDashboard, 30000);
      }
    } catch (e: any) {
      setDashboardError(e.message || "Dashboard data failed to load");
    }
  }, []);

  const loadProducts = useCallback(async () => {
    try {
      const res = await fetch("/api/products", { cache: "no-store" });
      const data = await res.json();
      setProducts(data.products || []);
    } catch {
      // handled inline by empty state
    }
  }, []);

  const loadKeywords = useCallback(async () => {
    try {
      const res = await fetch("/api/keywords", { cache: "no-store" });
      const data = await res.json();
      setKeywords(data.keywords || []);
    } catch {
      // handled inline by empty state
    }
  }, []);

  const loadAll = useCallback(async () => {
    await Promise.all([loadDashboard(), loadProducts(), loadKeywords()]);
  }, [loadDashboard, loadProducts, loadKeywords]);

  useEffect(() => {
    loadAll().finally(() => setLoading(false));
    const interval = setInterval(loadDashboard, 300000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const postAction = useCallback(
    async (url: string, body: any, successMsg: string, key: string) => {
      setBusy(key);
      try {
        const res = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body || {}),
        });
        const data = await res.json().catch(() => ({}));
        if (res.status === 202) {
          showToast("⏱ " + (data.message || "Report not ready yet"), true);
          return;
        }
        if (res.status === 404) {
          showToast("ℹ️ No pending report found. Run Full Optimization first.", true);
          return;
        }
        if (!res.ok || data.error) throw new Error(data.message || data.error || "Request failed");
        showToast(successMsg);
        setTimeout(loadDashboard, 1500);
      } catch (e: any) {
        showToast("❌ " + e.message, true);
      } finally {
        setBusy(null);
      }
    },
    [loadDashboard, showToast]
  );

  const refreshCache = () =>
    postAction("/api/refresh-dashboard-cache", {}, "✅ Cache refreshed with latest Amazon data!", "cache");
  const applyNegatives = () =>
    postAction(
      "/api/apply-negatives",
      { lookback_days: 14, refresh_cache_after: true },
      "✅ Negatives applied!",
      "negatives"
    );
  const applyWinners = () =>
    postAction(
      "/api/apply-winners",
      { lookback_days: 14, winner_bid: 0.9, refresh_cache_after: true },
      "✅ Winners added with peak/off-peak bids!",
      "winners"
    );
  const retuneBids = () =>
    postAction("/api/retune-existing-bids", {}, "✅ Bids retuned! High for peak, low for off-peak.", "retune");
  const applyEstimatedBids = () => {
    if (!confirm("Apply estimated bids to existing enabled keywords now?")) return;
    postAction(
      "/api/apply-estimated-bids",
      { apply_live: true, max_campaigns: 50, max_keywords_per_campaign: 100 },
      "✅ Estimated bids applied to existing keywords.",
      "estimated"
    );
  };
  const fullOptimize = () =>
    postAction(
      "/api/run-daily-optimization",
      { apply_negatives_live: true, apply_winners_live: true, lookback_days: 14, winner_bid: 0.9 },
      "✅ Report requested. Use “Apply Pending Report” in 30–60 min to apply results.",
      "optimize"
    );
  const applyPendingOptimization = () =>
    postAction("/api/apply-optimization", {}, "✅ Pending report applied.", "pending");

  const setCampaignState = async (campaignId: string, newState: "ENABLED" | "PAUSED") => {
    const label = newState === "PAUSED" ? "Pause" : "Resume";
    if (!confirm(`${label} campaign ${campaignId}?`)) return;
    showToast(`⏳ ${label} in progress...`);
    try {
      const res = await fetch(`/api/campaigns/${encodeURIComponent(campaignId)}/state`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ state: newState }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.error) throw new Error(data.message || data.error || "Failed");
      showToast(`✅ Campaign ${campaignId} is now ${newState}`);
      setTimeout(loadDashboard, 1200);
    } catch (e: any) {
      showToast("❌ " + e.message, true);
    }
  };

  const loadCampaignPlan = async () => {
    try {
      const res = await fetch("/api/campaign-plan", { cache: "no-store" });
      const data = await res.json();
      if (!res.ok || data.error) throw new Error(data.message || data.error || "Failed to load plan");
      setDiagPlan(data);
    } catch (e: any) {
      showToast(e.message, true);
    }
  };

  const loadCampaignDiagnostics = async () => {
    try {
      const res = await fetch("/api/campaigns-debug", { cache: "no-store" });
      const data = await res.json();
      if (!res.ok || data.error) throw new Error(data.message || data.error || "Failed to check status");
      setDiagStats(data);
    } catch (e: any) {
      showToast(e.message, true);
    }
  };

  const openLaunch = async (p: Product) => {
    setLaunchProduct(p);
    setLaunchBudget((+(p.suggested_budget || 25)).toFixed(2));
    setLaunchBid((+(p.suggested_bid || 0.85)).toFixed(2));
    const fallback = +(p.suggested_bid || 0.85);
    setLaunchPreview({ low: money(fallback * 0.7), mid: money(fallback), high: money(fallback * 1.3) });

    try {
      const qs = new URLSearchParams({
        asin: p.asin || "",
        keyword: p.title || "",
        fallback_bid: String(fallback || 0.85),
      });
      const res = await fetch(`/api/bid-recommendation?${qs.toString()}`, { cache: "no-store" });
      const data = await res.json();
      if (res.ok && !data.error) {
        setLaunchPreview({
          low: data.low != null ? money(data.low) : money(fallback * 0.7),
          mid: data.suggested != null ? money(data.suggested) : money(fallback),
          high: data.high != null ? money(data.high) : money(fallback * 1.3),
        });
        const mode = (data.bid_mode || dashboardData?.bid_mode || "NORMAL").toUpperCase();
        const autoBid = mode === "PEAK" ? data.high : mode === "OFF_PEAK" ? data.low : data.suggested;
        if (autoBid != null) setLaunchBid((+autoBid).toFixed(2));
      }
    } catch {
      // keep fallback preview values
    }
  };

  const closeLaunch = () => setLaunchProduct(null);

  const doLaunch = async () => {
    if (!launchProduct) return;
    const budget = +launchBudget;
    const bid = +launchBid;
    if (!isFinite(budget) || budget < 1) {
      showToast("❌ Daily budget must be at least $1.00", true);
      return;
    }
    if (!isFinite(bid) || bid < 0.02) {
      showToast("❌ Starting bid must be at least $0.02", true);
      return;
    }
    setLaunching(true);
    try {
      const res = await fetch("/api/campaigns/launch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          product_id: launchProduct.product_id,
          daily_budget: +budget.toFixed(2),
          starting_bid: +bid.toFixed(2),
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.error) throw new Error(data.message || data.error || "Launch failed");
      closeLaunch();
      if (data.duplicate_launch_prevented) {
        showToast("✅ Duplicate prevented — matching launch campaigns already exist.");
      } else {
        const created = data.campaigns_created || [];
        const auto = created.find((c: any) => c.campaign_type === "AUTO_DISCOVERY") || {};
        const exact = created.find((c: any) => c.campaign_type === "MANUAL_EXACT") || {};
        const count = data.keyword_filtering?.exact_keywords_selected || exact.keywords_count || 0;
        showToast(
          `✅ Launched AUTO ${auto.campaign_id || "—"} + EXACT ${exact.campaign_id || "—"} with ${count} exact keywords`
        );
      }
      setTimeout(loadAll, 2200);
    } catch (e: any) {
      showToast("❌ " + e.message, true);
    } finally {
      setLaunching(false);
    }
  };

  const bidMode = (dashboardData?.bid_mode || "UNKNOWN").toUpperCase();
  const summary = dashboardData?.summary || {};
  const allCampaigns: Campaign[] = dashboardData?.campaigns || [];
  const enabledCampaigns = allCampaigns.filter((c) => (c.state || "").toUpperCase() === "ENABLED");
  const pausedCampaigns = allCampaigns.filter((c) => (c.state || "").toUpperCase() === "PAUSED");

  const filteredProducts = useMemo(() => {
    const q = prodSearch.toLowerCase();
    if (!q) return products;
    return products.filter(
      (p) =>
        (p.title || "").toLowerCase().includes(q) ||
        (p.sku || "").toLowerCase().includes(q) ||
        (p.asin || "").toLowerCase().includes(q)
    );
  }, [products, prodSearch]);

  const bannerLabel =
    bidMode === "PEAK"
      ? "🟢 PEAK HOURS — High-end Amazon bids active"
      : bidMode === "OFF_PEAK"
      ? "🔵 OFF-PEAK — Low-end Amazon bids active"
      : bidMode === "NORMAL"
      ? "🟡 NORMAL HOURS — Mid-range Amazon bids active"
      : "⚪ UNKNOWN — waiting for data";

  const bannerRule =
    bidMode === "PEAK" ? "Using: suggestedBidHigh" : bidMode === "OFF_PEAK" ? "Using: suggestedBidLow" : "Using: (low+high)/2";

  const bannerColorClass =
    bidMode === "PEAK"
      ? "bg-nws-accent/[0.07] border-nws-accent/30"
      : bidMode === "OFF_PEAK"
      ? "bg-nws-blue/[0.07] border-nws-blue/30"
      : bidMode === "NORMAL"
      ? "bg-nws-warn/[0.07] border-nws-warn/25"
      : "bg-nws-muted/[0.07] border-nws-border";

  const bannerTagColor =
    bidMode === "PEAK"
      ? "text-nws-accent"
      : bidMode === "OFF_PEAK"
      ? "text-nws-blue"
      : bidMode === "NORMAL"
      ? "text-nws-warn"
      : "text-nws-muted";

  const bannerPillColor =
    bidMode === "PEAK"
      ? "bg-nws-accent/15 text-nws-accent"
      : bidMode === "OFF_PEAK"
      ? "bg-nws-blue/15 text-nws-blue"
      : bidMode === "NORMAL"
      ? "bg-nws-warn/[0.12] text-nws-warn"
      : "bg-nws-muted/[0.12] text-nws-muted";

  return (
    <div className="min-h-screen bg-nws-bg text-nws-text">
      <header className="px-9 py-[22px] border-b border-nws-border flex items-center justify-between gap-4 flex-wrap bg-nws-surface">
        <div className="font-display text-xl font-extrabold text-nws-accent">
          Nature&apos;s Way Soil <span className="text-nws-muted font-semibold text-sm ml-1.5">/ Amazon Ad Manager</span>
        </div>
        <div className="flex gap-2 flex-wrap items-center">
          <button className={`${btnGhost} ${btnSm}`} onClick={loadAll}>
            ⟳ Refresh
          </button>
          <Link href="/products" className={`${btnGhost} ${btnSm}`}>
            Manage Catalog
          </Link>
          <button className={`${btnGhost} ${btnSm}`} onClick={refreshCache} disabled={busy === "cache"}>
            {busy === "cache" ? <span className="nws-loader" /> : null} Refresh Cache
          </button>
          <button className={`${btnWarn} ${btnSm}`} onClick={applyNegatives} disabled={busy === "negatives"}>
            {busy === "negatives" ? <span className="nws-loader" /> : null} Apply Negatives
          </button>
          <button className={`${btnAccent} ${btnSm}`} onClick={applyWinners} disabled={busy === "winners"}>
            {busy === "winners" ? <span className="nws-loader" /> : null} Add Winners
          </button>
          <button className={`${btnBlue} ${btnSm}`} onClick={retuneBids} disabled={busy === "retune"}>
            {busy === "retune" ? <span className="nws-loader" /> : null} ↻ Retune Bids
          </button>
          <button className={`${btnBlue} ${btnSm}`} onClick={applyEstimatedBids} disabled={busy === "estimated"}>
            {busy === "estimated" ? <span className="nws-loader" /> : null} ≈ Apply Estimated Bids
          </button>
          <button className={`${btnWarn} ${btnSm}`} onClick={applyPendingOptimization} disabled={busy === "pending"}>
            {busy === "pending" ? <span className="nws-loader" /> : null} ⏱ Apply Pending Report
          </button>
          <button className={`${btnPrimary} !px-[22px] !py-2.5 !text-xs`} onClick={fullOptimize} disabled={busy === "optimize"}>
            {busy === "optimize" ? <span className="nws-loader" /> : null} ▶ Full Optimization
          </button>
        </div>
      </header>

      <div className="px-9 border-b border-nws-border bg-nws-surface flex">
        {(["campaigns", "products", "keywords"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`font-mono text-[11px] font-medium px-5 py-[13px] uppercase tracking-wider border-b-2 transition ${
              tab === t ? "text-nws-accent border-nws-accent" : "text-nws-muted border-transparent hover:text-nws-text"
            }`}
          >
            {t === "campaigns" ? "Campaigns" : t === "products" ? "Products & Launch" : "Keywords"}
          </button>
        ))}
      </div>

      <main className="px-9 py-7">
        {/* BID MODE BANNER */}
        <div className={`rounded-card px-5 py-3.5 mb-5 flex items-center justify-between gap-3 flex-wrap border ${bannerColorClass}`}>
          <div className="flex items-center gap-3.5 flex-wrap">
            <div className={`font-display text-[13px] font-bold tracking-wide ${bannerTagColor}`}>{bannerLabel}</div>
            <div className="text-[11px] text-nws-muted">
              Peak window: {dashboardData?.peak_hours_label || "10:00–20:59"} EST · Cache:{" "}
              {dashboardData?.refreshed_at ? new Date(dashboardData.refreshed_at).toLocaleString() : "—"} ·{" "}
              {dashboardData?.note || ""}
            </div>
          </div>
          <div className={`text-[11px] px-2.5 py-[3px] rounded-full font-medium ${bannerPillColor}`}>{bannerRule}</div>
        </div>

        {/* SUMMARY */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3.5 mb-6">
          <div className="bg-nws-surface border border-nws-border rounded-card px-5 py-4">
            <div className="text-[9px] uppercase tracking-widest text-nws-muted mb-1.5">Total Spend (14d)</div>
            <div className="font-display text-2xl font-bold">{money(summary.spend)}</div>
          </div>
          <div className="bg-nws-surface border border-nws-border rounded-card px-5 py-4">
            <div className="text-[9px] uppercase tracking-widest text-nws-muted mb-1.5">Total Sales (14d)</div>
            <div className="font-display text-2xl font-bold text-nws-accent">{money(summary.sales)}</div>
          </div>
          <div className="bg-nws-surface border border-nws-border rounded-card px-5 py-4">
            <div className="text-[9px] uppercase tracking-widest text-nws-muted mb-1.5">Portfolio ACoS</div>
            <div className={`font-display text-2xl font-bold ${acosClass(summary.acos)}`}>{pct(summary.acos)}</div>
          </div>
          <div className="bg-nws-surface border border-nws-border rounded-card px-5 py-4">
            <div className="text-[9px] uppercase tracking-widest text-nws-muted mb-1.5">Clicks / Orders</div>
            <div className="font-display text-2xl font-bold text-nws-blue">
              {summary.clicks || 0} / {summary.orders || 0}
            </div>
          </div>
        </div>

        {loading ? (
          <div className="text-center py-14 text-nws-muted text-xs">Loading...</div>
        ) : (
          <>
            {tab === "campaigns" && (
              <div>
                <div className="flex items-center justify-between gap-3 flex-wrap mb-4">
                  <div className="font-display text-base font-bold">
                    Active Campaigns{" "}
                    <span className="text-xs text-nws-muted font-mono font-normal">
                      ({enabledCampaigns.length} enabled / {pausedCampaigns.length} paused)
                    </span>
                  </div>
                  <div className="text-[11px] text-nws-muted">ENABLED only · 14-day window · bids from Amazon suggested range</div>
                </div>

                {dashboardError ? (
                  <div className="text-center py-14 px-5 text-nws-muted text-xs">
                    <div className="text-3xl mb-2.5">⚠️</div>
                    <div className="font-display text-lg text-nws-text mb-2">Dashboard data failed to load</div>
                    <div className="max-w-2xl mx-auto mb-4 leading-relaxed">{dashboardError}</div>
                    <div className="flex gap-2.5 justify-center flex-wrap">
                      <button className={btnAccent} onClick={() => setTab("products")}>
                        View Products
                      </button>
                      <button className={btnBlue} onClick={loadCampaignPlan}>
                        View Campaign Plan
                      </button>
                      <button className={btnGhost} onClick={loadCampaignDiagnostics}>
                        Check Amazon Status
                      </button>
                    </div>
                    <DiagPanels plan={diagPlan} stats={diagStats} />
                  </div>
                ) : dashboardData?.cache_rebuild_in_progress && enabledCampaigns.length === 0 ? (
                  <div className="text-center py-14 px-5 text-nws-muted text-xs">
                    <div className="text-3xl mb-2.5">⏳</div>
                    <div className="font-display text-lg text-nws-text mb-2">Building dashboard cache</div>
                    <div className="max-w-2xl mx-auto mb-2 leading-relaxed">
                      Pulling fresh campaign data from Amazon — this can take several minutes on cold start.
                    </div>
                    <div className="text-[10px] text-nws-muted">The page will auto-refresh while the rebuild is running.</div>
                  </div>
                ) : enabledCampaigns.length === 0 ? (
                  <div className="text-center py-14 px-5 text-nws-muted text-xs">
                    <div className="text-3xl mb-2.5">📭</div>
                    <div className="font-display text-lg text-nws-text mb-2">No enabled campaigns found</div>
                    <div className="max-w-2xl mx-auto mb-4 leading-relaxed">
                      The dashboard is connected, but this Amazon Ads profile is not returning enabled campaigns. This usually
                      means campaigns are paused, the wrong profile ID is selected, or new campaigns have not been launched yet.
                    </div>
                    <div className="flex gap-2.5 justify-center flex-wrap">
                      <button className={btnAccent} onClick={() => setTab("products")}>
                        View Products &amp; Launch
                      </button>
                      <button className={btnBlue} onClick={loadCampaignPlan}>
                        View Campaign Plan
                      </button>
                      <button className={btnGhost} onClick={loadCampaignDiagnostics}>
                        Check Amazon Status
                      </button>
                    </div>
                    <DiagPanels plan={diagPlan} stats={diagStats} />
                  </div>
                ) : (
                  <div className="grid gap-3.5" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(370px, 1fr))" }}>
                    {enabledCampaigns.map((c) => {
                      const cid = c.campaignId || "—";
                      const name = c.campaignName || c.name || "Unnamed";
                      const budget = c.budget?.budget != null ? money(c.budget.budget) : "—";
                      const mode = (c.currentBidMode || bidMode || "UNKNOWN").toUpperCase();
                      let low = c.amazonSuggestedBidLow;
                      let high = c.amazonSuggestedBidHigh;
                      const applied = c.currentAppliedBid;
                      let estimated = false;
                      if (low == null || high == null) {
                        const est = estimateBidWindow(c, applied);
                        low = est.low;
                        high = est.high;
                        estimated = true;
                      }
                      return (
                        <div key={cid} className="bg-nws-surface border border-nws-border rounded-card p-5 hover:border-nws-accent/30 transition">
                          <div className="flex items-start justify-between gap-2.5 mb-4">
                            <div>
                              <div className="font-display text-[13px] font-bold leading-snug">{name}</div>
                              <div className="text-[10px] text-nws-muted mt-1">ID: {cid}</div>
                            </div>
                            <span className="text-[10px] px-2.5 py-[3px] rounded-full font-medium bg-nws-accent/15 text-nws-accent whitespace-nowrap">
                              ENABLED
                            </span>
                          </div>
                          <div className="grid grid-cols-3 gap-2.5 mt-3">
                            <div>
                              <div className="text-[9px] uppercase tracking-wider text-nws-muted mb-1">Budget/Day</div>
                              <div className="text-sm font-medium">{budget}</div>
                            </div>
                            <div>
                              <div className="text-[9px] uppercase tracking-wider text-nws-muted mb-1">Spend</div>
                              <div className="text-sm font-medium">{money(c.spend)}</div>
                            </div>
                            <div>
                              <div className="text-[9px] uppercase tracking-wider text-nws-muted mb-1">Sales</div>
                              <div className="text-sm font-medium text-nws-accent">{money(c.sales)}</div>
                            </div>
                          </div>
                          <div className="grid grid-cols-3 gap-2.5 mt-3">
                            <div>
                              <div className="text-[9px] uppercase tracking-wider text-nws-muted mb-1">Impressions</div>
                              <div className="text-sm font-medium">{c.impressions || 0}</div>
                            </div>
                            <div>
                              <div className="text-[9px] uppercase tracking-wider text-nws-muted mb-1">Clicks</div>
                              <div className="text-sm font-medium">{c.clicks || 0}</div>
                            </div>
                            <div>
                              <div className="text-[9px] uppercase tracking-wider text-nws-muted mb-1">ACoS</div>
                              <div className={`text-sm font-medium ${acosClass(c.acos)}`}>{pct(c.acos)}</div>
                            </div>
                          </div>
                          <div className="bg-nws-surface2 rounded-[10px] px-3.5 py-3 mt-3">
                            <div className="text-[9px] uppercase tracking-wider text-nws-muted mb-2.5 flex items-center justify-between">
                              <span>{estimated ? "Estimated Bid Window (preview)" : "Amazon Suggested Bid Window"}</span>
                              <span className="inline-flex items-center gap-1.5">
                                <span
                                  className={`text-[9px] px-2 py-0.5 rounded-full font-bold ${
                                    estimated ? "bg-nws-warn/20 text-nws-warn" : "bg-nws-accent/20 text-nws-accent2"
                                  }`}
                                >
                                  {estimated ? "ESTIMATED" : "LIVE"}
                                </span>
                                <span className="text-[9px] px-2 py-0.5 rounded-full font-semibold bg-nws-muted/[0.12] text-nws-muted">
                                  {mode}
                                </span>
                              </span>
                            </div>
                            <div className="grid grid-cols-3 gap-2 text-center">
                              <div>
                                <div className="text-[9px] text-nws-muted mb-1">OFF-PEAK (low)</div>
                                <div className="text-[13px] font-semibold text-nws-blue">{money(low)}</div>
                              </div>
                              <div>
                                <div className="text-[9px] text-nws-muted mb-1">APPLIED BID</div>
                                <div className="text-[13px] font-semibold text-nws-warn">
                                  {applied != null ? money(applied) : "—"}
                                </div>
                              </div>
                              <div>
                                <div className="text-[9px] text-nws-muted mb-1">PEAK (high)</div>
                                <div className="text-[13px] font-semibold text-nws-accent">{money(high)}</div>
                              </div>
                            </div>
                          </div>
                          <div className="flex justify-end mt-3">
                            <button className={`${btnDanger} ${btnSm}`} onClick={() => setCampaignState(cid, "PAUSED")}>
                              ⏸ Pause
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {tab === "products" && (
              <div>
                <div className="flex items-center justify-between gap-3 flex-wrap mb-4">
                  <div className="font-display text-base font-bold">
                    Products <span className="text-xs text-nws-muted font-mono font-normal">({products.length})</span>
                  </div>
                  <div className="text-[11px] text-nws-muted">Click Launch to create a live Amazon SP campaign for that product</div>
                </div>
                <div className="bg-nws-surface border border-nws-border rounded-card overflow-hidden">
                  <div className="px-[18px] py-3.5 border-b border-nws-border flex gap-2.5 items-center flex-wrap">
                    <input
                      className="font-mono text-xs bg-nws-surface2 border border-nws-border text-nws-text px-3.5 py-2 rounded-[7px] outline-none focus:border-nws-accent w-64 placeholder:text-nws-muted"
                      placeholder="Filter by title, SKU, ASIN…"
                      value={prodSearch}
                      onChange={(e) => setProdSearch(e.target.value)}
                    />
                    <span className="text-[10px] text-nws-muted">
                      {filteredProducts.length} / {products.length}
                    </span>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead className="bg-nws-surface2">
                        <tr>
                          {["", "Title", "SKU", "ASIN", "Price", "Budget", "Bid", "Action"].map((h) => (
                            <th
                              key={h}
                              className="text-[9px] font-medium uppercase tracking-wider text-nws-muted px-3.5 py-[11px] text-left border-b border-nws-border whitespace-nowrap"
                            >
                              {h}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {filteredProducts.length === 0 ? (
                          <tr>
                            <td colSpan={8} className="text-center py-10 text-nws-muted text-xs">
                              No matches
                            </td>
                          </tr>
                        ) : (
                          filteredProducts.map((p) => (
                            <tr key={p.product_id} className="hover:bg-nws-accent/[0.04] transition border-b border-nws-border last:border-b-0">
                              <td className="px-3.5 py-3">
                                <span className={`inline-block w-1.5 h-1.5 rounded-full ${p.active ? "bg-nws-accent" : "bg-nws-danger"}`} />
                              </td>
                              <td className="px-3.5 py-3 max-w-xs text-xs leading-snug">{p.title || "—"}</td>
                              <td className="px-3.5 py-3 text-xs whitespace-nowrap">{p.sku || "—"}</td>
                              <td className="px-3.5 py-3 text-xs">
                                {p.asin ? (
                                  <span className="text-[10px] bg-nws-surface2 text-nws-accent border border-nws-accent/20 px-1.5 py-0.5 rounded">
                                    {p.asin}
                                  </span>
                                ) : (
                                  "—"
                                )}
                              </td>
                              <td className="px-3.5 py-3 text-xs">{p.price ? money(+p.price) : "—"}</td>
                              <td className="px-3.5 py-3 text-xs">{money(p.suggested_budget ?? 25)}</td>
                              <td className="px-3.5 py-3 text-xs">{money(p.suggested_bid ?? 0.85)}</td>
                              <td className="px-3.5 py-3">
                                <button className={`${btnPrimary} ${btnSm}`} onClick={() => openLaunch(p)}>
                                  Launch
                                </button>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {tab === "keywords" && (
              <div>
                <div className="flex items-center justify-between gap-3 flex-wrap mb-4">
                  <div className="font-display text-base font-bold">
                    Keyword Performance <span className="text-xs text-nws-muted font-mono font-normal">({keywords.length})</span>
                  </div>
                </div>
                <div className="bg-nws-surface border border-nws-border rounded-card overflow-hidden overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-nws-surface2">
                      <tr>
                        {["Keyword", "Match", "Campaign", "Bid", "30d Clicks", "30d Conv", "30d Cost", "30d Sales", "ACOS"].map(
                          (h) => (
                            <th
                              key={h}
                              className="text-[9px] font-medium uppercase tracking-wider text-nws-muted px-3.5 py-[11px] text-left border-b border-nws-border whitespace-nowrap"
                            >
                              {h}
                            </th>
                          )
                        )}
                      </tr>
                    </thead>
                    <tbody>
                      {keywords.length === 0 ? (
                        <tr>
                          <td colSpan={9} className="text-center py-10 text-nws-muted text-xs">
                            No keywords found. Run the sync job to import data.
                          </td>
                        </tr>
                      ) : (
                        keywords.map((kw) => (
                          <tr key={kw.keyword_id} className="hover:bg-nws-accent/[0.04] transition border-b border-nws-border last:border-b-0">
                            <td className="px-3.5 py-3 text-xs font-medium">{kw.keyword_text}</td>
                            <td className="px-3.5 py-3 text-xs text-nws-muted">{kw.match_type}</td>
                            <td className="px-3.5 py-3 text-xs text-nws-muted max-w-xs truncate" title={kw.campaign_name}>
                              {kw.campaign_name}
                            </td>
                            <td className="px-3.5 py-3 text-xs">{money(kw.current_bid)}</td>
                            <td className="px-3.5 py-3 text-xs">{kw.clicks_30d ?? 0}</td>
                            <td className="px-3.5 py-3 text-xs">{kw.conversions_30d ?? 0}</td>
                            <td className="px-3.5 py-3 text-xs">{money(kw.cost_30d)}</td>
                            <td className="px-3.5 py-3 text-xs">{money(kw.sales_30d)}</td>
                            <td className={`px-3.5 py-3 text-xs ${acosClass(kw.acos)}`}>
                              {kw.sales_30d ? pct(kw.acos) : "—"}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}
      </main>

      {/* LAUNCH MODAL */}
      {launchProduct && (
        <div
          className="fixed inset-0 bg-nws-bg/[0.88] z-[1000] flex items-center justify-center p-5"
          onClick={(e) => {
            if (e.target === e.currentTarget) closeLaunch();
          }}
        >
          <div className="bg-nws-surface border border-nws-border rounded-2xl p-7 w-full max-w-[520px]">
            <div className="font-display text-[17px] font-bold text-nws-accent mb-1">🚀 Launch Campaign</div>
            <div className="text-[11px] text-nws-muted mb-5">
              Launching SP campaign for ASIN: {launchProduct.asin || launchProduct.sku}
            </div>
            <div className="mb-3.5">
              <div className="text-[10px] text-nws-muted uppercase tracking-wide mb-1.5">Product</div>
              <div className="bg-nws-surface2 border border-nws-border rounded-[7px] px-3.5 py-2.5 text-xs">
                {launchProduct.title || "—"}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 mb-3.5">
              <div>
                <div className="text-[10px] text-nws-muted uppercase tracking-wide mb-1.5">ASIN</div>
                <div className="bg-nws-surface2 border border-nws-border rounded-[7px] px-3.5 py-2.5 text-xs">
                  {launchProduct.asin || "—"}
                </div>
              </div>
              <div>
                <div className="text-[10px] text-nws-muted uppercase tracking-wide mb-1.5">SKU</div>
                <div className="bg-nws-surface2 border border-nws-border rounded-[7px] px-3.5 py-2.5 text-xs">
                  {launchProduct.sku || "—"}
                </div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 mb-3.5">
              <div>
                <div className="text-[10px] text-nws-muted uppercase tracking-wide mb-1.5">Daily Budget ($)</div>
                <input
                  type="number"
                  step="0.01"
                  min="1"
                  value={launchBudget}
                  onChange={(e) => setLaunchBudget(e.target.value)}
                  className="font-mono text-[13px] bg-nws-surface2 border border-nws-border text-nws-text px-3.5 py-2.5 rounded-[7px] w-full outline-none focus:border-nws-accent"
                />
              </div>
              <div>
                <div className="text-[10px] text-nws-muted uppercase tracking-wide mb-1.5">Starting Bid ($)</div>
                <input
                  type="number"
                  step="0.01"
                  min="0.02"
                  value={launchBid}
                  onChange={(e) => setLaunchBid(e.target.value)}
                  className="font-mono text-[13px] bg-nws-surface2 border border-nws-border text-nws-text px-3.5 py-2.5 rounded-[7px] w-full outline-none focus:border-nws-accent"
                />
              </div>
            </div>
            <div className="text-[10px] text-nws-muted uppercase tracking-wide mb-2">Amazon Suggested Bid Range (live)</div>
            <div className="bg-nws-surface2 border border-nws-border rounded-lg px-3.5 py-2.5 grid grid-cols-3 gap-2 text-center mb-3.5">
              <div>
                <div className="text-[9px] text-nws-muted uppercase tracking-wide mb-1">Off-Peak (Low)</div>
                <div className="text-[13px] font-semibold text-nws-blue">{launchPreview.low ?? "—"}</div>
              </div>
              <div>
                <div className="text-[9px] text-nws-muted uppercase tracking-wide mb-1">Suggested Mid</div>
                <div className="text-[13px] font-semibold text-nws-warn">{launchPreview.mid ?? "—"}</div>
              </div>
              <div>
                <div className="text-[9px] text-nws-muted uppercase tracking-wide mb-1">Peak (High)</div>
                <div className="text-[13px] font-semibold text-nws-accent">{launchPreview.high ?? "—"}</div>
              </div>
            </div>
            <div className="mb-1">
              <div className="text-[10px] text-nws-muted uppercase tracking-wide mb-1.5">Keywords (auto-generated)</div>
              <div className="bg-nws-surface2 border border-nws-border rounded-[7px] px-3.5 py-2.5 text-[10px] leading-relaxed max-h-20 overflow-y-auto text-nws-muted">
                {launchProduct.keywords || launchProduct.research_keywords
                  ? [launchProduct.keywords, launchProduct.research_keywords].filter(Boolean).join(", ")
                  : "Auto-generated from title + category"}
              </div>
            </div>
            <div className="flex gap-2 justify-end mt-5">
              <button className={btnGhost} onClick={closeLaunch}>
                Cancel
              </button>
              <button className={btnPrimary} onClick={doLaunch} disabled={launching}>
                {launching ? (
                  <>
                    <span className="nws-loader" /> Launching...
                  </>
                ) : (
                  "🚀 Launch Live Campaign"
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* TOAST */}
      {toastMsg && (
        <div
          className={`fixed bottom-6 right-6 z-[2000] bg-nws-surface border border-nws-border rounded-[10px] px-4 py-3.5 text-xs max-w-[320px] leading-relaxed shadow-2xl border-l-[3px] ${
            toastMsg.err ? "border-l-nws-danger" : "border-l-nws-accent"
          }`}
        >
          {toastMsg.msg}
        </div>
      )}
    </div>
  );
}

function DiagPanels({ plan, stats }: { plan: any; stats: any }) {
  if (!plan && !stats) return null;
  return (
    <div className="mt-5 max-w-2xl mx-auto text-left space-y-3">
      {plan && (
        <div className="bg-nws-surface2 border border-nws-border rounded-xl p-4">
          <div className="font-display text-nws-accent mb-2 text-sm">Campaign Plan Ready</div>
          <div className="text-xs text-nws-muted leading-relaxed">
            Products in plan: <b className="text-nws-text">{plan.product_count ?? "—"}</b>
          </div>
        </div>
      )}
      {stats && (
        <div className="bg-nws-surface2 border border-nws-border rounded-xl p-4">
          <div className="font-display text-nws-accent mb-2.5 text-sm">Amazon Campaign Status</div>
          <div className="grid grid-cols-3 gap-2.5">
            <div>
              <div className="text-[9px] text-nws-muted uppercase tracking-wide mb-1">Enabled</div>
              <div className="text-sm font-medium text-nws-accent">{stats.enabled_count}</div>
            </div>
            <div>
              <div className="text-[9px] text-nws-muted uppercase tracking-wide mb-1">Paused</div>
              <div className="text-sm font-medium text-nws-warn">{stats.paused_count}</div>
            </div>
            <div>
              <div className="text-[9px] text-nws-muted uppercase tracking-wide mb-1">Archived</div>
              <div className="text-sm font-medium">{stats.archived_count}</div>
            </div>
          </div>
          <div className="text-[11px] text-nws-muted mt-3.5 leading-relaxed">{stats.message || "Diagnostic check complete."}</div>
        </div>
      )}
    </div>
  );
}
