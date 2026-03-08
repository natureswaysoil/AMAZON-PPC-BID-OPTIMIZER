'use client';

import { useEffect, useState } from 'react';

interface Campaign {
  campaign_id: number;
  campaign_name: string;
  state: string;
  daily_budget: number;
  keyword_count: number;
  cost_7d: number;
  sales_7d: number;
  acos_7d: number;
}

export default function CampaignsTable({ onSelectCampaign }: { onSelectCampaign: (id: number) => void }) {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchCampaigns();
  }, []);

  async function fetchCampaigns() {
    try {
      const response = await fetch('/api/campaigns');
      const data = await response.json();
      setCampaigns(data.campaigns || []);
    } catch (error) {
      console.error('Failed to fetch campaigns:', error);
    } finally {
      setLoading(false);
    }
  }

  if (loading) return <div>Loading campaigns...</div>;

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Campaign</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Budget</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Keywords</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Spend (7d)</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Sales (7d)</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">ACOS</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {campaigns.map((campaign) => (
            <tr key={campaign.campaign_id} className="hover:bg-gray-50">
              <td className="px-6 py-4 whitespace-nowrap">
                <div className="text-sm font-medium text-gray-900">{campaign.campaign_name}</div>
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <span className={`px-2 py-1 text-xs rounded-full ${
                  campaign.state === 'ENABLED' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                }`}>
                  {campaign.state}
                </span>
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                ${campaign.daily_budget?.toFixed(2) || '0.00'}
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                {campaign.keyword_count || 0}
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                ${campaign.cost_7d?.toFixed(2) || '0.00'}
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                ${campaign.sales_7d?.toFixed(2) || '0.00'}
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <span className={`text-sm font-medium ${
                  campaign.acos_7d > 0.35 ? 'text-red-600' : 
                  campaign.acos_7d > 0.25 ? 'text-yellow-600' : 'text-green-600'
                }`}>
                  {(campaign.acos_7d * 100)?.toFixed(1) || '0.0'}%
                </span>
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm">
                <button
                  onClick={() => onSelectCampaign(campaign.campaign_id)}
                  className="text-blue-600 hover:text-blue-800"
                >
                  View Keywords
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
