'use client';

import { useEffect, useState } from 'react';

interface Keyword {
  keyword_id: number;
  keyword_text: string;
  match_type: string;
  current_bid: number;
  suggested_bid: number;
  state: string;
  aov_tier: string;
  performance_tier: string;
  clicks_30d: number;
  conversions_30d: number;
  cost_30d: number;
  sales_30d: number;
  acos: number;
  reasoning: string;
}

export default function KeywordsTable({ campaignId }: { campaignId: number | null }) {
  const [keywords, setKeywords] = useState<Keyword[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedKeywords, setSelectedKeywords] = useState<Set<number>>(new Set());

  useEffect(() => {
    fetchKeywords();
  }, [campaignId]);

  async function fetchKeywords() {
    try {
      const url = campaignId 
        ? `/api/keywords?campaign_id=${campaignId}`
        : '/api/keywords';
      const response = await fetch(url);
      const data = await response.json();
      setKeywords(data.keywords || []);
    } catch (error) {
      console.error('Failed to fetch keywords:', error);
    } finally {
      setLoading(false);
    }
  }

  async function applyBidChanges() {
    const keywordsToUpdate = keywords.filter(k => selectedKeywords.has(k.keyword_id));
    
    try {
      const response = await fetch('/api/optimize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keywords: keywordsToUpdate })
      });
      
      if (response.ok) {
        alert('Bid changes applied successfully!');
        setSelectedKeywords(new Set());
        fetchKeywords();
      }
    } catch (error) {
      console.error('Failed to apply changes:', error);
      alert('Failed to apply bid changes');
    }
  }

  function toggleKeyword(keywordId: number) {
    const newSelected = new Set(selectedKeywords);
    if (newSelected.has(keywordId)) {
      newSelected.delete(keywordId);
    } else {
      newSelected.add(keywordId);
    }
    setSelectedKeywords(newSelected);
  }

  if (loading) return <div>Loading keywords...</div>;

  return (
    <div className="space-y-4">
      {selectedKeywords.size > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex justify-between items-center">
          <span className="text-blue-800">
            {selectedKeywords.size} keyword(s) selected
          </span>
          <button
            onClick={applyBidChanges}
            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
          >
            Apply Bid Changes
          </button>
        </div>
      )}

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3"></th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Keyword</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Match</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Tier</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Current Bid</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Suggested Bid</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Clicks</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Conv.</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">ACOS</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Details</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {keywords.map((keyword) => {
              const bidChange = keyword.suggested_bid ? 
                ((keyword.suggested_bid - keyword.current_bid) / keyword.current_bid * 100) : 0;
              
              return (
                <tr key={keyword.keyword_id} className="hover:bg-gray-50">
                  <td className="px-6 py-4">
                    {keyword.suggested_bid && keyword.suggested_bid !== keyword.current_bid && (
                      <input
                        type="checkbox"
                        checked={selectedKeywords.has(keyword.keyword_id)}
                        onChange={() => toggleKeyword(keyword.keyword_id)}
                        className="rounded"
                      />
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <div className="text-sm font-medium text-gray-900">{keyword.keyword_text}</div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="text-xs px-2 py-1 bg-gray-100 rounded">{keyword.match_type}</span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-1">
                      <TierBadge tier={keyword.aov_tier} type="aov" />
                      <TierBadge tier={keyword.performance_tier} type="perf" />
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm">${keyword.current_bid?.toFixed(2)}</td>
                  <td className="px-6 py-4">
                    {keyword.suggested_bid ? (
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">${keyword.suggested_bid.toFixed(2)}</span>
                        <span className={`text-xs ${bidChange > 0 ? 'text-green-600' : 'text-red-600'}`}>
                          ({bidChange > 0 ? '+' : ''}{bidChange.toFixed(0)}%)
                        </span>
                      </div>
                    ) : (
                      <span className="text-gray-400 text-sm">-</span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-sm">{keyword.clicks_30d || 0}</td>
                  <td className="px-6 py-4 text-sm">{keyword.conversions_30d || 0}</td>
                  <td className="px-6 py-4">
                    <span className={`text-sm font-medium ${
                      keyword.acos > 0.35 ? 'text-red-600' : 
                      keyword.acos > 0.25 ? 'text-yellow-600' : 'text-green-600'
                    }`}>
                      {(keyword.acos * 100)?.toFixed(1) || '0.0'}%
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    {keyword.reasoning && (
                      <button
                        className="text-blue-600 text-sm hover:text-blue-800"
                        onClick={() => alert(keyword.reasoning)}
                      >
                        View
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TierBadge({ tier, type }: { tier: string, type: 'aov' | 'perf' }) {
  if (!tier) return null;
  
  const colors = type === 'aov' 
    ? { L: 'bg-gray-100 text-gray-700', M: 'bg-blue-100 text-blue-700', H: 'bg-purple-100 text-purple-700', X: 'bg-pink-100 text-pink-700' }
    : { A: 'bg-green-100 text-green-700', B: 'bg-blue-100 text-blue-700', C: 'bg-yellow-100 text-yellow-700', D: 'bg-orange-100 text-orange-700', E: 'bg-red-100 text-red-700' };
  
  return (
    <span className={`text-xs px-2 py-1 rounded ${colors[tier as keyof typeof colors] || 'bg-gray-100'}`}>
      {tier}
    </span>
  );
}
