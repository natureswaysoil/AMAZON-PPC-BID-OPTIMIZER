'use client';

import { useEffect, useState } from 'react';

export default function SettingsPanel() {
  const [settings, setSettings] = useState<any>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchSettings();
  }, []);

  async function fetchSettings() {
    try {
      const response = await fetch('/api/settings');
      const data = await response.json();
      setSettings(data);
    } catch (error) {
      console.error('Failed to fetch settings:', error);
    } finally {
      setLoading(false);
    }
  }

  async function saveSettings() {
    setSaving(true);
    try {
      const response = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
      });
      
      if (response.ok) {
        alert('Settings saved successfully!');
      }
    } catch (error) {
      console.error('Failed to save settings:', error);
      alert('Failed to save settings');
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div>Loading settings...</div>;

  return (
    <div className="max-w-4xl space-y-6">
      {/* Global Settings */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Global Bid Settings</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Target ACOS (%)</label>
            <input
              type="number"
              step="1"
              value={(settings.target_acos * 100) || 30}
              onChange={(e) => setSettings({...settings, target_acos: Number(e.target.value) / 100})}
              className="w-full px-3 py-2 border rounded"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Min Bid ($)</label>
            <input
              type="number"
              step="0.01"
              value={settings.min_bid || 0.30}
              onChange={(e) => setSettings({...settings, min_bid: Number(e.target.value)})}
              className="w-full px-3 py-2 border rounded"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Max Bid ($)</label>
            <input
              type="number"
              step="0.01"
              value={settings.max_bid || 5.00}
              onChange={(e) => setSettings({...settings, max_bid: Number(e.target.value)})}
              className="w-full px-3 py-2 border rounded"
            />
          </div>
        </div>
      </div>

      {/* Time-Based Settings */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Time-Based Optimization</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Peak Hours (Select hours)</label>
            <div className="grid grid-cols-6 md:grid-cols-12 gap-2">
              {Array.from({ length: 24 }, (_, i) => i).map(hour => (
                <label key={hour} className="flex items-center">
                  <input
                    type="checkbox"
                    checked={settings.peak_hours?.includes(hour)}
                    onChange={(e) => {
                      const newHours = e.target.checked
                        ? [...(settings.peak_hours || []), hour]
                        : (settings.peak_hours || []).filter((h: number) => h !== hour);
                      setSettings({...settings, peak_hours: newHours.sort()});
                    }}
                    className="mr-1"
                  />
                  <span className="text-sm">{hour}h</span>
                </label>
              ))}
            </div>
          </div>
          
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Peak Multiplier</label>
              <input
                type="number"
                step="0.1"
                value={settings.peak_multiplier || 1.10}
                onChange={(e) => setSettings({...settings, peak_multiplier: Number(e.target.value)})}
                className="w-full px-3 py-2 border rounded"
              />
              <p className="text-xs text-gray-500 mt-1">e.g., 1.10 = +10% bids</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Off-Peak Multiplier</label>
              <input
                type="number"
                step="0.1"
                value={settings.offpeak_multiplier || 0.90}
                onChange={(e) => setSettings({...settings, offpeak_multiplier: Number(e.target.value)})}
                className="w-full px-3 py-2 border rounded"
              />
              <p className="text-xs text-gray-500 mt-1">e.g., 0.90 = -10% bids</p>
            </div>
          </div>
        </div>
      </div>

      {/* AOV Tiers */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">AOV Tier Settings</h3>
        <div className="space-y-4">
          {settings.aov_tiers && Object.entries(settings.aov_tiers).map(([tier, config]: [string, any]) => (
            <div key={tier} className="grid grid-cols-4 gap-4 pb-4 border-b">
              <div className="font-semibold text-lg">Tier {tier}</div>
              <div>
                <label className="block text-xs text-gray-500">Min AOV</label>
                <input
                  type="number"
                  value={config.min}
                  onChange={(e) => setSettings({
                    ...settings,
                    aov_tiers: {
                      ...settings.aov_tiers,
                      [tier]: {...config, min: Number(e.target.value)}
                    }
                  })}
                  className="w-full px-2 py-1 border rounded text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500">Max AOV</label>
                <input
                  type="number"
                  value={config.max}
                  onChange={(e) => setSettings({
                    ...settings,
                    aov_tiers: {
                      ...settings.aov_tiers,
                      [tier]: {...config, max: Number(e.target.value)}
                    }
                  })}
                  className="w-full px-2 py-1 border rounded text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500">Max Bid Ceiling</label>
                <input
                  type="number"
                  step="0.01"
                  value={config.ceiling}
                  onChange={(e) => setSettings({
                    ...settings,
                    aov_tiers: {
                      ...settings.aov_tiers,
                      [tier]: {...config, ceiling: Number(e.target.value)}
                    }
                  })}
                  className="w-full px-2 py-1 border rounded text-sm"
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Automation Controls */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Automation</h3>
        <label className="flex items-center">
          <input
            type="checkbox"
            checked={settings.enable_auto_bidding}
            onChange={(e) => setSettings({...settings, enable_auto_bidding: e.target.checked})}
            className="mr-3 h-5 w-5"
          />
          <div>
            <span className="font-medium">Enable Automatic Bid Optimization</span>
            <p className="text-sm text-gray-600">System will automatically adjust bids every 2 hours during prime time</p>
          </div>
        </label>
      </div>

      {/* Save Button */}
      <div className="flex justify-end gap-4">
        <button
          onClick={fetchSettings}
          className="px-6 py-2 border border-gray-300 rounded hover:bg-gray-50"
        >
          Reset
        </button>
        <button
          onClick={saveSettings}
          disabled={saving}
          className="px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Save Settings'}
        </button>
      </div>
    </div>
  );
}
