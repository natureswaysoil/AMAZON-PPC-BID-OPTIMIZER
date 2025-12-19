// frontend/components/dashboard/AlertsPanel.tsx
'use client'

import { useEffect, useState } from 'react'
import { Alert } from '@/types'

export default function AlertsPanel() {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [loading, setLoading] = useState(true)
  
  useEffect(() => {
    fetchAlerts()
  }, [])
  
  async function fetchAlerts() {
    try {
      const response = await fetch('/api/alerts')
      const data = await response.json()
      setAlerts(data.alerts)
    } catch (error) {
      console.error('Failed to fetch alerts:', error)
    } finally {
      setLoading(false)
    }
  }
  
  const criticalAlerts = alerts.filter(a => a.severity === 'CRITICAL')
  const highAlerts = alerts.filter(a => a.severity === 'HIGH')
  
  if (loading) return <div>Loading alerts...</div>
  
  if (alerts.length === 0) {
    return (
      <div className="bg-green-50 border border-green-200 rounded-lg p-4">
        <p className="text-green-800">✅ All systems operating normally</p>
      </div>
    )
  }
  
  return (
    <div className="space-y-4">
      {criticalAlerts.length > 0 && (
        <div className="bg-red-50 border-l-4 border-red-500 p-4">
          <h3 className="text-red-900 font-semibold mb-2">
            🚨 {criticalAlerts.length} Critical Alert{criticalAlerts.length > 1 ? 's' : ''}
          </h3>
          {criticalAlerts.map(alert => (
            <AlertCard key={alert.alert_id} alert={alert} />
          ))}
        </div>
      )}
      
      {highAlerts.length > 0 && (
        <div className="bg-orange-50 border-l-4 border-orange-500 p-4">
          <h3 className="text-orange-900 font-semibold mb-2">
            ⚠️ {highAlerts.length} High Priority Alert{highAlerts.length > 1 ? 's' : ''}
          </h3>
          {highAlerts.map(alert => (
            <AlertCard key={alert.alert_id} alert={alert} />
          ))}
        </div>
      )}
    </div>
  )
}

function AlertCard({ alert }: { alert: Alert }) {
  const [expanded, setExpanded] = useState(false)
  
  return (
    <div className="bg-white rounded-lg shadow p-4 mb-3">
      <div className="flex justify-between items-start">
        <div className="flex-1">
          <p className="font-medium text-gray-900">{alert.message}</p>
          <p className="text-sm text-gray-500 mt-1">
            {alert.entity_type}: {alert.data.product_name || alert.data.campaign_name}
          </p>
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-blue-600 text-sm hover:text-blue-800"
        >
          {expanded ? 'Less' : 'More'}
        </button>
      </div>
      
      {expanded && (
        <div className="mt-4 border-t pt-4">
          <h4 className="font-semibold text-sm mb-2">Action Items:</h4>
          <ul className="list-disc list-inside space-y-1">
            {alert.action_items.map((item, idx) => (
              <li key={idx} className="text-sm text-gray-700">{item}</li>
            ))}
          </ul>
          
          <div className="mt-4 bg-gray-50 p-3 rounded text-sm">
            <h4 className="font-semibold mb-2">Details:</h4>
            <pre className="text-xs overflow-auto">
              {JSON.stringify(alert.data, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}
