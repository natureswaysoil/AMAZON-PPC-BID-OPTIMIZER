// frontend/components/dashboard/PerformanceCharts.tsx
'use client'

import { useEffect, useState } from 'react'
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts'

export default function PerformanceCharts() {
  const [performanceData, setPerformanceData] = useState([])
  const [timeRange, setTimeRange] = useState('7d')
  
  useEffect(() => {
    fetchPerformanceData(timeRange)
  }, [timeRange])
  
  async function fetchPerformanceData(range: string) {
    const response = await fetch(`/api/performance?range=${range}`)
    const data = await response.json()
    setPerformanceData(data)
  }
  
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-xl font-semibold">Performance Trends</h2>
        <div className="flex gap-2">
          {['7d', '30d', '90d'].map(range => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className={`px-4 py-2 rounded ${
                timeRange === range
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {range}
            </button>
          ))}
        </div>
      </div>
      
      {/* ACOS Trend */}
      <div className="mb-8">
        <h3 className="text-lg font-medium mb-4">ACOS Trend</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={performanceData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line
              type="monotone"
              dataKey="acos"
              stroke="#ef4444"
              strokeWidth={2}
              name="ACOS"
            />
            <Line
              type="monotone"
              dataKey="target_acos"
              stroke="#10b981"
              strokeWidth={2}
              strokeDasharray="5 5"
              name="Target ACOS"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      
      {/* Spend & Sales */}
      <div className="mb-8">
        <h3 className="text-lg font-medium mb-4">Spend vs Sales</h3>
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={performanceData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Area
              type="monotone"
              dataKey="sales"
              stackId="1"
              stroke="#3b82f6"
              fill="#3b82f6"
              name="Sales"
            />
            <Area
              type="monotone"
              dataKey="cost"
              stackId="2"
              stroke="#ef4444"
              fill="#ef4444"
              name="Ad Spend"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      
      {/* Hourly Performance Heatmap */}
      <div>
        <h3 className="text-lg font-medium mb-4">Performance by Hour</h3>
        <HourlyHeatmap />
      </div>
    </div>
  )
}

function HourlyHeatmap() {
  const [heatmapData, setHeatmapData] = useState([])
  
  useEffect(() => {
    fetchHeatmapData()
  }, [])
  
  async function fetchHeatmapData() {
    const response = await fetch('/api/performance/hourly')
    const data = await response.json()
    setHeatmapData(data)
  }
  
  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={heatmapData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="hour" />
        <YAxis />
        <Tooltip />
        <Legend />
        <Bar dataKey="roas" fill="#10b981" name="ROAS" />
        <Bar dataKey="acos" fill="#ef4444" name="ACOS" />
      </BarChart>
    </ResponsiveContainer>
  )
}
