"use client";

import { useState, useEffect } from "react";
import Link from "next/link";

interface Product {
  sku: string;
  asin: string;
  product_name: string;
  total_keywords: number;
  campaign_count: number;
  estimated_daily_budget: number;
}

interface Campaign {
  campaign_type: string;
  campaign_name: string;
  daily_budget: number;
  default_bid: number;
  keyword_count: number;
  keywords: Array<{ keywordText: string; matchType: string }>;
}

interface CampaignPlan {
  product_name: string;
  product_sku: string;
  asin: string;
  campaigns: Campaign[];
  harvested_keywords: Array<{ keywordText: string; matchType: string }>;
  total_keywords: number;
  target_acos: number;
  estimated_daily_budget: number;
}

export default function CampaignBuilder() {
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedSku, setSelectedSku] = useState<string>("");
  const [campaignPlan, setCampaignPlan] = useState<CampaignPlan | null>(null);
  const [dailyBudget, setDailyBudget] = useState<number | "">("");
  const [startingBid, setStartingBid] = useState<number | "">("");
  const [loading, setLoading] = useState(false);
  const [dryRun, setDryRun] = useState(true);
  const [creationResult, setCreationResult] = useState<any>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    fetchProducts();
  }, []);

  const fetchProducts = async () => {
    try {
      setLoading(true);
      const response = await fetch("/api/campaigns/products");
      const data = await response.json();
      setProducts(data.products || []);
    } catch (err) {
      setError("Failed to load products");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleProductSelect = async (sku: string) => {
    setSelectedSku(sku);
    setCampaignPlan(null);
    setCreationResult(null);

    try {
      setLoading(true);
      const response = await fetch("/api/campaigns/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sku }),
      });
      const data = await response.json();
      if (response.ok) {
        setCampaignPlan(data);
        setError("");
      } else {
        setError(data.error || "Failed to load campaign preview");
      }
    } catch (err) {
      setError("Failed to preview campaign");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateCampaign = async () => {
    if (!selectedSku) {
      setError("Please select a product");
      return;
    }

    try {
      setLoading(true);
      const response = await fetch("/api/campaigns/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sku: selectedSku,
          daily_budget: dailyBudget || null,
          starting_bid: startingBid || null,
          dry_run: dryRun,
        }),
      });
      const data = await response.json();
      if (response.ok) {
        setCreationResult(data);
        setError("");
      } else {
        setError(data.error || "Failed to create campaign");
      }
    } catch (err) {
      setError("Failed to create campaign");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <Link href="/" className="text-emerald-400 hover:text-emerald-300 mb-4 inline-block">
            ← Back to Dashboard
          </Link>
          <h1 className="text-4xl font-bold text-white mb-2">Campaign Builder</h1>
          <p className="text-gray-300">Create new campaigns from your product sheet</p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-900/30 border border-red-700 rounded-lg text-red-300">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Product Selection */}
          <div className="lg:col-span-1">
            <div className="bg-slate-700/40 backdrop-blur border border-slate-600/50 rounded-lg p-6">
              <h2 className="text-xl font-bold text-white mb-4">Select Product</h2>

              <div className="space-y-2 max-h-96 overflow-y-auto">
                {loading && products.length === 0 ? (
                  <p className="text-gray-400">Loading products...</p>
                ) : products.length === 0 ? (
                  <p className="text-gray-400">No products available</p>
                ) : (
                  products.map((product) => (
                    <button
                      key={product.sku}
                      onClick={() => handleProductSelect(product.sku)}
                      className={`w-full text-left p-3 rounded border transition ${
                        selectedSku === product.sku
                          ? "bg-emerald-900/50 border-emerald-500"
                          : "bg-slate-600/30 border-slate-600/50 hover:bg-slate-600/50"
                      }`}
                    >
                      <div className="font-medium text-white text-sm">{product.product_name}</div>
                      <div className="text-xs text-gray-400 mt-1">SKU: {product.sku}</div>
                      <div className="text-xs text-gray-400">
                        {product.campaign_count} campaigns, {product.total_keywords} keywords
                      </div>
                    </button>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* Campaign Preview & Creation */}
          <div className="lg:col-span-2">
            {campaignPlan ? (
              <div className="space-y-6">
                {/* Plan Summary */}
                <div className="bg-slate-700/40 backdrop-blur border border-slate-600/50 rounded-lg p-6">
                  <h2 className="text-xl font-bold text-white mb-4">Campaign Plan</h2>

                  <div className="grid grid-cols-2 gap-4 mb-6">
                    <div>
                      <div className="text-sm text-gray-400">Product</div>
                      <div className="text-lg font-medium text-white">{campaignPlan.product_name}</div>
                    </div>
                    <div>
                      <div className="text-sm text-gray-400">ASIN</div>
                      <div className="text-lg font-medium text-emerald-400">{campaignPlan.asin}</div>
                    </div>
                    <div>
                      <div className="text-sm text-gray-400">Campaigns</div>
                      <div className="text-lg font-medium text-white">{campaignPlan.campaigns.length}</div>
                    </div>
                    <div>
                      <div className="text-sm text-gray-400">Total Keywords</div>
                      <div className="text-lg font-medium text-white">{campaignPlan.total_keywords}</div>
                    </div>
                  </div>

                  {/* Estimated Budget */}
                  <div className="mb-6 p-4 bg-slate-600/30 rounded border border-slate-600/50">
                    <div className="text-sm text-gray-400 mb-2">Estimated Daily Budget</div>
                    <div className="text-2xl font-bold text-emerald-400">
                      ${campaignPlan.estimated_daily_budget.toFixed(2)}
                    </div>
                  </div>

                  {/* Campaign Details */}
                  <div className="space-y-3">
                    <h3 className="font-medium text-white">Campaigns to Create:</h3>
                    {campaignPlan.campaigns.map((campaign, idx) => (
                      <div key={idx} className="p-3 bg-slate-600/20 rounded border border-slate-600/30">
                        <div className="font-medium text-white">{campaign.campaign_type}</div>
                        <div className="text-sm text-gray-400 mt-1">
                          Budget: ${campaign.daily_budget.toFixed(2)}/day | Bid: ${campaign.default_bid.toFixed(2)} | {campaign.keyword_count} keywords
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Options */}
                <div className="bg-slate-700/40 backdrop-blur border border-slate-600/50 rounded-lg p-6">
                  <h3 className="text-lg font-bold text-white mb-4">Configuration</h3>

                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-2">
                        Daily Budget (optional)
                      </label>
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        value={dailyBudget}
                        onChange={(e) => setDailyBudget(e.target.value ? parseFloat(e.target.value) : "")}
                        placeholder="Use product defaults"
                        className="w-full px-4 py-2 bg-slate-600/30 border border-slate-600/50 rounded text-white placeholder-gray-500 focus:outline-none focus:border-emerald-500"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-2">
                        Starting Bid (optional)
                      </label>
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        value={startingBid}
                        onChange={(e) => setStartingBid(e.target.value ? parseFloat(e.target.value) : "")}
                        placeholder="Use product defaults"
                        className="w-full px-4 py-2 bg-slate-600/30 border border-slate-600/50 rounded text-white placeholder-gray-500 focus:outline-none focus:border-emerald-500"
                      />
                    </div>

                    <div className="flex items-center">
                      <input
                        type="checkbox"
                        id="dry-run"
                        checked={dryRun}
                        onChange={(e) => setDryRun(e.target.checked)}
                        className="w-4 h-4 accent-emerald-500"
                      />
                      <label htmlFor="dry-run" className="ml-2 text-sm font-medium text-gray-300">
                        Dry Run (Preview Only)
                      </label>
                    </div>
                  </div>

                  <button
                    onClick={handleCreateCampaign}
                    disabled={loading}
                    className="w-full mt-6 px-4 py-3 bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-600 text-white font-medium rounded transition"
                  >
                    {loading ? "Creating..." : `${dryRun ? "Preview" : "Launch"} Campaigns`}
                  </button>
                </div>
              </div>
            ) : selectedSku ? (
              <div className="bg-slate-700/40 backdrop-blur border border-slate-600/50 rounded-lg p-6 text-center">
                <p className="text-gray-400">
                  {loading ? "Loading campaign preview..." : "Select a product to see campaign details"}
                </p>
              </div>
            ) : (
              <div className="bg-slate-700/40 backdrop-blur border border-slate-600/50 rounded-lg p-6 text-center">
                <p className="text-gray-400">Select a product from the left to get started</p>
              </div>
            )}

            {/* Creation Results */}
            {creationResult && (
              <div className="mt-6 bg-slate-700/40 backdrop-blur border border-emerald-600/50 rounded-lg p-6">
                <h3 className="text-lg font-bold text-emerald-400 mb-4">
                  {dryRun ? "Preview Results" : "Campaign Creation Results"}
                </h3>
                <pre className="text-sm text-gray-300 overflow-auto bg-slate-900/50 p-4 rounded">
                  {JSON.stringify(creationResult, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
