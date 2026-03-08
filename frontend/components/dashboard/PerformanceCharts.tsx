'use client';

import { useEffect, useState } from 'react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

export default function PerformanceCharts() {
  const [data, setData] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPerformanceData();
  }, []);

  async function fetchPerformanceData() {
    try {
      const response = await fetch('/api/performance');
      const result = await response.json();
      setData(result.daily || []);
      setSummary(result.summary || {});
    } catch (error) {
      console.error('Failed to fetch performance:', error);
    } finally {
      setLoading(false);
    }
  }

  if (loading) return <div>Loading...</div>;

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <SummaryCard
          title="Total Spend (7d)"
          value={`$${summary.total_spend?.toFixed(2) || '0.00'}`}
          change={summary.spend_change}
          icon="💰"
        />
        <SummaryCard
          title="Total Sales (7d)"
          value={`$${summary.total_sales?.toFixed(2) || '0.00'}`}
          change={summary.sales_change}
          icon="📈"
        />
        <SummaryCard
          title="ACOS"
          value={`${(summary.acos * 100)?.toFixed(1) || '0.0'}%`}
          change={summary.acos_change}
          icon="🎯"
          invertChange
        />
        <SummaryCard
          title="ROAS"
          value={`${summary.roas?.toFixed(2) || '0.00'}x`}
          change={summary.roas_change}
          icon="⚡"
        />
      </div>

      {/* Daily Performance Chart */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Daily Performance (Last 30 Days)</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis yAxisId="left" />
            <YAxis yAxisId="right" orientation="right" />
            <Tooltip />
            <Legend />
            <Line yAxisId="left" type="monotone" dataKey="spend" stroke="#ef4444" name="Spend" />
            <Line yAxisId="left" type="monotone" dataKey="sales" stroke="#10b981" name="Sales" />
            <Line yAxisId="right" type="monotone" dataKey="acos" stroke="#f59e0b" name="ACOS" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* AOV Tier Performance */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Performance by AOV Tier</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={summary.by_tier || []}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="tier" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="spend" fill="#3b82f6" name="Spend" />
            <Bar dataKey="sales" fill="#10b981" name="Sales" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function SummaryCard({ title, value, change, icon, invertChange = false }: any) {
  const isPositive = invertChange ? change < 0 : change > 0;
  const changeColor = isPositive ? 'text-green-600' : 'text-red-600';
  
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500">{title}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
          {change !== undefined && (
            <p className={`text-sm mt-1 ${changeColor}`}>
              {change > 0 ? '+' : ''}{change?.toFixed(1)}% vs last week
            </p>
          )}
        </div>
        <div className="text-4xl">{icon}</div>
      </div>
    </div>
  );
}
