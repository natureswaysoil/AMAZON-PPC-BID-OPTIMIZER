// frontend/components/settings/OptimizationSettings.tsx
'use client'

import { useState, useEffect } from 'react'
import { useForm } from 'react-hook-form'

type Settings = {
  target_acos: number
  min_bid: number
  max_bid: number
  peak_hours: number[]
  peak_multiplier: number
  offpeak_multiplier: number
  enable_auto_bidding: boolean
  enable_keyword_harvesting: boolean
  min_orders_to_harvest: number
  inventory_warning_days: number
}

export default function OptimizationSettings() {
  const [loading, setLoading] = useState(false)
  const [saved, setSaved] = useState(false)
  
  const { register, handleSubmit, reset, watch } = useForm<Settings>()
  
  useEffect(() => {
    fetchSettings()
  }, [])
  
  async function fetchSettings() {
    const response = await fetch('/api/settings')
    const data = await response.json()
    reset(data)
  }
  
  async function onSubmit(data: Settings) {
    setLoading(true)
    try {
      await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (error) {
      console.error('Failed to save settings:', error)
    } finally {
      setLoading(false)
    }
  }
  
  const enableAutoBidding = watch('enable_auto_bidding')
  
  return (
    <div className="max-w-4xl mx-auto bg-white rounded-lg shadow p-6">
      <h2 className="text-2xl font-bold mb-6">Optimization Settings</h2>
      
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* Global Settings */}
        <div className="border-b pb-6">
          <h3 className="text-lg font-semibold mb-4">Global Bid Settings</h3>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Target ACOS (%)
              </label>
              <input
                type="number"
                step="0.01"
                {...register('target_acos')}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
              <p className="text-xs text-gray-500 mt-1">
                Default target for campaigns
              </p>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Minimum Bid ($)
              </label>
              <input
                type="number"
                step="0.01"
                {...register('min_bid')}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Maximum Bid ($)
              </label>
              <input
                type="number"
                step="0.01"
                {...register('max_bid')}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
            </div>
          </div>
        </div>
        
        {/* Time-Based Optimization */}
        <div className="border-b pb-6">
          <h3 className="text-lg font-semibold mb-4">Time-Based Optimization</h3>
          
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Peak Hours (Select hours with best performance)
            </label>
            <div className="grid grid-cols-6 md:grid-cols-12 gap-2">
              {Array.from({ length: 24 }, (_, i) => i).map(hour => (
                <label key={hour} className="flex items-center">
                  <input
                    type="checkbox"
                    value={hour}
                    {...register('peak_hours')}
                    className="mr-1"
                  />
                  <span className="text-sm">{hour}h</span>
                </label>
              ))}
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Peak Hours Multiplier
              </label>
              <input
                type="number"
                step="0.1"
                {...register('peak_multiplier')}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
              <p className="text-xs text-gray-500 mt-1">
                Bid increase during peak hours (e.g., 1.3 = +30%)
              </p>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Off-Peak Multiplier
              </label>
              <input
                type="number"
                step="0.1"
                {...register('offpeak_multiplier')}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
              <p className="text-xs text-gray-500 mt-1">
                Bid reduction during off-peak (e.g., 0.5 = -50%)
              </p>
            </div>
          </div>
        </div>
        
        {/* Automation Controls */}
        <div className="border-b pb-6">
          <h3 className="text-lg font-semibold mb-4">Automation Controls</h3>
          
          <div className="space-y-4">
            <label className="flex items-center">
              <input
                type="checkbox"
                {...register('enable_auto_bidding')}
                className="mr-3 h-5 w-5"
              />
              <div>
                <span className="font-medium">Enable Automatic Bid Optimization</span>
                <p className="text-sm text-gray-600">
                  System will automatically adjust bids based on performance
                </p>
              </div>
            </label>
            
            <label className="flex items-center">
              <input
                type="checkbox"
                {...register('enable_keyword_harvesting')}
                className="mr-3 h-5 w-5"
              />
              <div>
                <span className="font-medium">Enable Automatic Keyword Harvesting</span>
                <p className="text-sm text-gray-600">
                  Automatically add high-performing search terms as keywords
                </p>
              </div>
            </label>
          </div>
        </div>
        
        {/* Keyword Harvesting Settings */}
        <div className="border-b pb-6">
          <h3 className="text-lg font-semibold mb-4">Keyword Harvesting</h3>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Minimum Orders to Harvest
              </label>
              <input
                type="number"
                {...register('min_orders_to_harvest')}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
              <p className="text-xs text-gray-500 mt-1">
                Search term must have this many orders before being added
              </p>
            </div>
          </div>
        </div>
        
        {/* Inventory & Alerts */}
        <div className="pb-6">
          <h3 className="text-lg font-semibold mb-4">Inventory & Alerts</h3>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Inventory Warning Threshold (days)
            </label>
            <input
              type="number"
              {...register('inventory_warning_days')}
              className="w-full md:w-1/2 px-3 py-2 border border-gray-300 rounded-md"
            />
            <p className="text-xs text-gray-500 mt-1">
              Alert when days of inventory cover falls below this threshold
            </p>
          </div>
        </div>
        
        {/* Submit Button */}
        <div className="flex justify-end gap-4">
          <button
            type="button"
            onClick={() => fetchSettings()}
            className="px-6 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
          >
            Reset
          </button>
          <button
            type="submit"
            disabled={loading}
            className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
        
        {saved && (
          <div className="text-green-600 text-sm text-right">
            ✓ Settings saved successfully
          </div>
        )}
      </form>
    </div>
  )
}
