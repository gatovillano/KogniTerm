'use client'

import { useState, useEffect, useCallback } from 'react'
import { Key, Check, ChevronDown, RefreshCw, ShieldAlert, Cpu } from 'lucide-react'

const PROVIDERS = ['google', 'openai', 'anthropic', 'openrouter', 'ollama', 'kilocode']

export function LLMConfig() {
  const [config, setConfig] = useState<Record<string, any>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [models, setModels] = useState<Record<string, string[]>>({})

  const API_BASE = 'http://localhost:8765'

  const fetchConfig = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/config/llm`)
      const data = await response.json()
      const newConfig: Record<string, any> = {}
      PROVIDERS.forEach(provider => {
        newConfig[provider] = data[provider] || { enabled: false, apiKey: '', defaultModel: '' }
      })
      setConfig(newConfig)
      setLoading(false)
    } catch (error) {
      setLoading(false)
    }
  }, [])

  const fetchModels = useCallback(async (provider: string) => {
    try {
      const response = await fetch(`${API_BASE}/models/available`)
      const data = await response.json()
      setModels(prev => ({ ...prev, [provider]: data.models || [] }))
    } catch (error) {
      console.error(error)
    }
  }, [])

  useEffect(() => {
    fetchConfig()
  }, [fetchConfig])

  const updateConfig = (provider: string, updates: Partial<any>) => {
    setConfig(prev => ({
      ...prev,
      [provider]: { ...prev[provider], ...updates },
    }))
  }

  const saveConfig = async () => {
    setSaving(true)
    try {
      await fetch(`${API_BASE}/config/llm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      })
    } catch (error) {
      console.error(error)
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="text-xs text-zinc-400 font-mono">Loading config...</div>

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between border-b border-zinc-200 dark:border-zinc-800 pb-3">
        <div className="flex items-center gap-2">
          <Cpu className="w-4 h-4 text-zinc-500 stroke-[1.5]" />
          <h2 className="text-xs font-medium uppercase tracking-wider text-zinc-500">LLM Providers</h2>
        </div>
        <button
          onClick={saveConfig}
          disabled={saving}
          className="text-xs font-mono px-3 py-1 bg-zinc-900 text-zinc-100 dark:bg-zinc-100 dark:text-zinc-900 rounded hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Save changes'}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {PROVIDERS.map(provider => (
          <div key={provider} className="border border-zinc-200 dark:border-zinc-800/80 rounded-lg p-3 bg-zinc-50/50 dark:bg-zinc-900/30 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium capitalize text-zinc-800 dark:text-zinc-200">{provider}</span>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={config[provider]?.enabled || false}
                  onChange={(e) => updateConfig(provider, { enabled: e.target.checked })}
                  className="sr-only peer"
                />
                <div className="w-7 h-4 bg-zinc-200 peer-focus:outline-none rounded-full peer dark:bg-zinc-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-zinc-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all dark:border-zinc-600 peer-checked:bg-zinc-900 dark:peer-checked:bg-zinc-100"></div>
              </label>
            </div>

            <div className="space-y-2">
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-2.5 flex items-center pointer-events-none">
                  <Key className="w-3 h-3 text-zinc-400 stroke-[1.5]" />
                </div>
                <input
                  type="password"
                  value={config[provider]?.apiKey || ''}
                  onChange={(e) => updateConfig(provider, { apiKey: e.target.value })}
                  className="w-full pl-8 pr-3 py-1 text-xs font-mono bg-white dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded focus:outline-none focus:border-zinc-400"
                  placeholder="API Key..."
                />
              </div>

              <div className="flex gap-2">
                <select
                  value={config[provider]?.defaultModel || ''}
                  onChange={(e) => updateConfig(provider, { defaultModel: e.target.value })}
                  className="flex-1 px-2 py-1 text-xs font-mono bg-white dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded focus:outline-none focus:border-zinc-400"
                  disabled={!config[provider]?.enabled}
                >
                  <option value="">Default model</option>
                  {(models[provider] || []).map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
                <button
                  onClick={() => fetchModels(provider)}
                  disabled={!config[provider]?.enabled}
                  className="p-1 border border-zinc-200 dark:border-zinc-800 rounded hover:bg-zinc-100 dark:hover:bg-zinc-800 disabled:opacity-30"
                  title="Fetch models"
                >
                  <RefreshCw className="w-3 h-3 text-zinc-500 stroke-[1.5]" />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
ENDOFFILE