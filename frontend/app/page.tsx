'use client';

import { useState } from 'react';
import Link from 'next/link';

export default function HomePage() {
  const [activeTab, setActiveTab] = useState('overview');

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex justify-between items-start">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">
              🚀 Amazon PPC Optimizer
            </h1>
            <p className="mt-1 text-sm text-gray-500">
              Live Amazon Sponsored Display optimization with AOV-aware dynamic bidding
            </p>
          </div>
          <div className="flex gap-3">
            <Link
              href="/products"
              className="px-4 py-2 bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 font-medium rounded"
            >
              Products
            </Link>
            <Link
              href="/campaigns"
              className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white font-medium rounded"
            >
              + New Campaign
            </Link>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-6">
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            {['overview', 'campaigns', 'keywords'].map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === tab
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </nav>
        </div>
      </div>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'overview' && <OverviewTab />}
        {activeTab === 'campaigns' && <CampaignsTab />}
        {activeTab === 'keywords' && <KeywordsTab />}
      </main>
    </div>
  );
}

function OverviewTab() {
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-semibold mb-4">System Status</h2>
      <div className="space-y-3">
        <StatusItem label="Live Data Sync" status="Active" />
        <StatusItem label="Bid Optimization" status="Active" />
        <StatusItem label="Campaign Type" status="Sponsored Display" />
        <StatusItem label="Auto-token Refresh" status="Enabled" />
      </div>
    </div>
  );
}

function CampaignsTab() {
  const [campaigns, setCampaigns] = React.useState([]);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    fetch('/api/campaigns')
      .then(r => r.json())
      .then(data => {
        setCampaigns(data.campaigns || []);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  }, []);

  if (loading) return <div>Loading campaigns...</div>;

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <div className="px-6 py-4 border-b">
        <h2 className="text-xl font-semibold">Your Campaigns ({campaigns.length})</h2>
      </div>
      {campaigns.length === 0 ? (
        <p className="text-gray-500 p-6">No campaigns found. Run the sync job to import data.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-500 text-left">
              <tr>
                <th className="px-6 py-3">Campaign</th>
                <th className="px-6 py-3">Budget</th>
                <th className="px-6 py-3">State</th>
                <th className="px-6 py-3">Keywords</th>
                <th className="px-6 py-3">7d Cost</th>
                <th className="px-6 py-3">7d Sales</th>
                <th className="px-6 py-3">7d ACOS</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {campaigns.map((camp: any) => (
                <tr key={camp.campaign_id} className="hover:bg-gray-50">
                  <td className="px-6 py-3 font-medium max-w-md truncate" title={camp.campaign_name}>
                    {camp.campaign_name}
                  </td>
                  <td className="px-6 py-3 text-gray-600">${camp.daily_budget ?? 0}/day</td>
                  <td className="px-6 py-3 text-gray-600">{camp.state}</td>
                  <td className="px-6 py-3 text-gray-600">{camp.keyword_count ?? 0}</td>
                  <td className="px-6 py-3 text-gray-600">${(camp.cost_7d ?? 0).toFixed(2)}</td>
                  <td className="px-6 py-3 text-gray-600">${(camp.sales_7d ?? 0).toFixed(2)}</td>
                  <td className="px-6 py-3 text-gray-600">
                    {camp.acos_7d != null ? `${(camp.acos_7d * 100).toFixed(1)}%` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function KeywordsTab() {
  const [keywords, setKeywords] = React.useState<any[]>([]);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    fetch('/api/keywords')
      .then(r => r.json())
      .then(data => {
        setKeywords(data.keywords || []);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  }, []);

  if (loading) return <div>Loading keywords...</div>;

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <div className="px-6 py-4 border-b">
        <h2 className="text-xl font-semibold">Keyword Performance ({keywords.length})</h2>
      </div>
      {keywords.length === 0 ? (
        <p className="text-gray-500 p-6">No keywords found. Run the sync job to import data.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-500 text-left">
              <tr>
                <th className="px-6 py-3">Keyword</th>
                <th className="px-6 py-3">Match</th>
                <th className="px-6 py-3">Campaign</th>
                <th className="px-6 py-3">Bid</th>
                <th className="px-6 py-3">30d Clicks</th>
                <th className="px-6 py-3">30d Conv</th>
                <th className="px-6 py-3">30d Cost</th>
                <th className="px-6 py-3">30d Sales</th>
                <th className="px-6 py-3">ACOS</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {keywords.map((kw: any) => (
                <tr key={kw.keyword_id} className="hover:bg-gray-50">
                  <td className="px-6 py-3 font-medium">{kw.keyword_text}</td>
                  <td className="px-6 py-3 text-gray-600">{kw.match_type}</td>
                  <td className="px-6 py-3 text-gray-600 max-w-xs truncate" title={kw.campaign_name}>
                    {kw.campaign_name}
                  </td>
                  <td className="px-6 py-3 text-gray-600">${kw.current_bid?.toFixed(2) ?? '0.00'}</td>
                  <td className="px-6 py-3 text-gray-600">{kw.clicks_30d ?? 0}</td>
                  <td className="px-6 py-3 text-gray-600">{kw.conversions_30d ?? 0}</td>
                  <td className="px-6 py-3 text-gray-600">${(kw.cost_30d ?? 0).toFixed(2)}</td>
                  <td className="px-6 py-3 text-gray-600">${(kw.sales_30d ?? 0).toFixed(2)}</td>
                  <td className="px-6 py-3 text-gray-600">
                    {kw.sales_30d ? `${(kw.acos * 100).toFixed(1)}%` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function StatusItem({ label, status }: { label: string; status: string }) {
  return (
    <div className="flex justify-between items-center p-3 bg-gray-50 rounded">
      <span className="font-medium">{label}</span>
      <span className="text-green-600">✓ {status}</span>
    </div>
  );
}

// Add React import at top
import React from 'react';
