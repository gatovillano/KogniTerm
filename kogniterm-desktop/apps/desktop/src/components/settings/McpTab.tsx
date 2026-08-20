import React, { useState, useEffect } from 'react';
import { 
  Server, Plus, Trash2, CheckCircle, AlertCircle, 
  Terminal, Globe, Loader2, Play, RefreshCw, Power
} from 'lucide-react';

export interface MCPServerConfig {
  transport: 'stdio' | 'sse';
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  url?: string;
  headers?: Record<string, string>;
  disabled?: boolean;
  status?: 'connected' | 'disconnected' | 'error' | 'disabled';
  tools?: string[];
  error?: string;
}

export const McpTab: React.FC = () => {
  const [servers, setServers] = useState<Record<string, MCPServerConfig>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [activeScope, setActiveScope] = useState<'global' | 'project'>('project');
  
  // Modal / Form state for Add/Edit
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [serverName, setServerName] = useState('');
  const [transport, setTransport] = useState<'stdio' | 'sse'>('stdio');
  const [command, setCommand] = useState('');
  const [argsInput, setArgsInput] = useState('');
  const [envInput, setEnvInput] = useState('');
  const [url, setUrl] = useState('');
  
  // Test Connection status
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ status: 'ok' | 'error', message?: string, tools?: string[] } | null>(null);

  useEffect(() => {
    fetchServers();
  }, []);

  const fetchServers = async () => {
    setIsLoading(true);
    try {
      const res = await fetch('http://localhost:8765/api/mcp/servers');
      if (res.ok) {
        const data = await res.json();
        setServers(data);
      }
    } catch (e) {
      console.error('Error fetching MCP servers:', e);
    } finally {
      setIsLoading(false);
    }
  };

  const handleToggle = async (name: string) => {
    try {
      const res = await fetch(`http://localhost:8765/api/mcp/servers/${encodeURIComponent(name)}/toggle?scope=${activeScope}`, {
        method: 'POST'
      });
      if (res.ok) {
        fetchServers();
      }
    } catch (e) {
      console.error('Error toggling MCP server:', e);
    }
  };

  const handleDelete = async (name: string) => {
    if (!confirm(`¿Eliminar la configuración del servidor MCP '${name}'?`)) return;
    try {
      const res = await fetch(`http://localhost:8765/api/mcp/servers/${encodeURIComponent(name)}?scope=${activeScope}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        fetchServers();
      }
    } catch (e) {
      console.error('Error deleting MCP server:', e);
    }
  };

  const handleTestConnection = async () => {
    setIsTesting(true);
    setTestResult(null);
    try {
      const args = argsInput.trim() ? argsInput.trim().split('\n').map(s => s.trim()) : [];
      let env: Record<string, string> = {};
      if (envInput.trim()) {
        try {
          env = JSON.parse(envInput);
        } catch {
          // parse line by line KEY=VALUE
          envInput.split('\n').forEach(line => {
            const idx = line.indexOf('=');
            if (idx > 0) {
              env[line.substring(0, idx).trim()] = line.substring(idx + 1).trim();
            }
          });
        }
      }

      const payload = {
        transport,
        command: transport === 'stdio' ? command.trim() : undefined,
        args: transport === 'stdio' ? args : undefined,
        env: transport === 'stdio' ? env : undefined,
        url: transport === 'sse' ? url.trim() : undefined
      };

      const res = await fetch('http://localhost:8765/api/mcp/test-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        const data = await res.json();
        setTestResult(data);
      } else {
        setTestResult({ status: 'error', message: 'Error de respuesta del servidor backend' });
      }
    } catch (e: any) {
      setTestResult({ status: 'error', message: e.message || 'Error de red al probar conexión' });
    } finally {
      setIsTesting(false);
    }
  };

  const handleSaveServer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!serverName.trim()) return;

    const args = argsInput.trim() ? argsInput.trim().split('\n').map(s => s.trim()) : [];
    let env: Record<string, string> = {};
    if (envInput.trim()) {
      try {
        env = JSON.parse(envInput);
      } catch {
        envInput.split('\n').forEach(line => {
          const idx = line.indexOf('=');
          if (idx > 0) {
            env[line.substring(0, idx).trim()] = line.substring(idx + 1).trim();
          }
        });
      }
    }

    const payload = {
      name: serverName.trim(),
      scope: activeScope,
      config: {
        transport,
        command: transport === 'stdio' ? command.trim() : undefined,
        args: transport === 'stdio' ? args : undefined,
        env: transport === 'stdio' ? env : undefined,
        url: transport === 'sse' ? url.trim() : undefined,
        disabled: false
      }
    };

    try {
      const res = await fetch('http://localhost:8765/api/mcp/servers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        setIsModalOpen(false);
        resetForm();
        fetchServers();
      }
    } catch (e) {
      console.error('Error saving MCP server:', e);
    }
  };

  const resetForm = () => {
    setServerName('');
    setTransport('stdio');
    setCommand('');
    setArgsInput('');
    setEnvInput('');
    setUrl('');
    setTestResult(null);
  };

  return (
    <div className="space-y-6">
      {/* Header and Scope Selector */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-100 flex items-center gap-2">
            <Server className="w-5 h-5 text-indigo-400" />
            Servidores MCP (Model Context Protocol)
          </h3>
          <p className="text-sm text-gray-400 mt-1">
            Conecta servidores MCP para expandir dinámicamente las herramientas de tus agentes.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex bg-gray-800 p-1 rounded-lg border border-gray-700">
            <button
              onClick={() => setActiveScope('project')}
              className={`px-3 py-1 text-xs rounded-md font-medium transition-all ${
                activeScope === 'project'
                  ? 'bg-indigo-600 text-white shadow'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              Proyecto
            </button>
            <button
              onClick={() => setActiveScope('global')}
              className={`px-3 py-1 text-xs rounded-md font-medium transition-all ${
                activeScope === 'global'
                  ? 'bg-indigo-600 text-white shadow'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              Global
            </button>
          </div>

          <button
            onClick={() => {
              resetForm();
              setIsModalOpen(true);
            }}
            className="flex items-center gap-2 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg shadow-sm transition-all"
          >
            <Plus className="w-4 h-4" />
            Agregar Servidor
          </button>
        </div>
      </div>

      {/* Server Cards List */}
      {isLoading ? (
        <div className="flex items-center justify-center p-8 text-gray-400">
          <Loader2 className="w-6 h-6 animate-spin mr-2" />
          Cargando servidores MCP...
        </div>
      ) : Object.keys(servers).length === 0 ? (
        <div className="text-center p-8 border border-dashed border-gray-700 rounded-xl bg-gray-900/50">
          <Server className="w-10 h-10 text-gray-500 mx-auto mb-3" />
          <h4 className="text-sm font-medium text-gray-300">No hay servidores MCP configurados</h4>
          <p className="text-xs text-gray-500 mt-1 max-w-md mx-auto">
            Puedes añadir servidores MCP locales ejecutable por stdio (ej. `npx -y @modelcontextprotocol/server-filesystem`) o remotos por SSE.
          </p>
        </div>
      ) : (
        <div className="grid gap-4">
          {Object.entries(servers).map(([name, config]) => (
            <div
              key={name}
              className={`p-4 rounded-xl border transition-all ${
                config.disabled
                  ? 'bg-gray-900/40 border-gray-800 opacity-60'
                  : config.status === 'error'
                  ? 'bg-red-950/20 border-red-800/40'
                  : 'bg-gray-800/60 border-gray-700'
              }`}
            >
              <div className="flex items-start justify-between">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-gray-100">{name}</span>
                    <span className="px-2 py-0.5 text-[10px] uppercase font-mono tracking-wider rounded bg-gray-700 text-gray-300">
                      {config.transport || 'stdio'}
                    </span>
                    {config.disabled ? (
                      <span className="flex items-center gap-1 text-xs text-gray-500">
                        <Power className="w-3 h-3" /> Desactivado
                      </span>
                    ) : config.status === 'connected' ? (
                      <span className="flex items-center gap-1 text-xs text-emerald-400">
                        <CheckCircle className="w-3.5 h-3.5" /> Conectado
                      </span>
                    ) : config.status === 'error' ? (
                      <span className="flex items-center gap-1 text-xs text-red-400">
                        <AlertCircle className="w-3.5 h-3.5" /> Error
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-xs text-gray-400">
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Inicializando
                      </span>
                    )}
                  </div>

                  <p className="text-xs font-mono text-gray-400">
                    {config.transport === 'sse'
                      ? config.url
                      : `${config.command} ${(config.args || []).join(' ')}`}
                  </p>

                  {/* Discovered Tools count */}
                  {config.tools && config.tools.length > 0 && (
                    <div className="mt-2 text-xs text-indigo-300">
                      🛠️ {config.tools.length} herramienta(s) disponible(s): {config.tools.join(', ')}
                    </div>
                  )}

                  {config.error && (
                    <div className="mt-1 text-xs text-red-400 bg-red-900/20 p-2 rounded border border-red-800/30">
                      {config.error}
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleToggle(name)}
                    title={config.disabled ? "Habilitar servidor" : "Deshabilitar servidor"}
                    className={`p-1.5 rounded-lg transition-colors ${
                      config.disabled
                        ? 'text-gray-500 hover:text-emerald-400 hover:bg-gray-700'
                        : 'text-emerald-400 hover:text-red-400 hover:bg-gray-700'
                    }`}
                  >
                    <Power className="w-4 h-4" />
                  </button>

                  <button
                    onClick={() => handleDelete(name)}
                    title="Eliminar servidor"
                    className="p-1.5 text-gray-400 hover:text-red-400 hover:bg-gray-700 rounded-lg transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add / Edit Server Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-gray-900 border border-gray-700 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <Server className="w-5 h-5 text-indigo-400" />
              Configurar Servidor MCP
            </h3>

            <form onSubmit={handleSaveServer} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-300 mb-1">Nombre del Servidor</label>
                <input
                  type="text"
                  required
                  placeholder="ej. filesystem, github, postgres"
                  value={serverName}
                  onChange={e => setServerName(e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-300 mb-1">Transporte</label>
                <div className="flex gap-4">
                  <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                    <input
                      type="radio"
                      name="transport"
                      value="stdio"
                      checked={transport === 'stdio'}
                      onChange={() => setTransport('stdio')}
                      className="text-indigo-600 focus:ring-indigo-500"
                    />
                    <Terminal className="w-4 h-4 text-gray-400" /> Stdio (Comando Local)
                  </label>
                  <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                    <input
                      type="radio"
                      name="transport"
                      value="sse"
                      checked={transport === 'sse'}
                      onChange={() => setTransport('sse')}
                      className="text-indigo-600 focus:ring-indigo-500"
                    />
                    <Globe className="w-4 h-4 text-gray-400" /> SSE (HTTP Remoto)
                  </label>
                </div>
              </div>

              {transport === 'stdio' ? (
                <>
                  <div>
                    <label className="block text-xs font-medium text-gray-300 mb-1">Comando Principal</label>
                    <input
                      type="text"
                      placeholder="npx, python, /path/to/binary"
                      value={command}
                      onChange={e => setCommand(e.target.value)}
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-indigo-500"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-gray-300 mb-1">Argumentos (uno por línea)</label>
                    <textarea
                      rows={3}
                      placeholder={"-y\n@modelcontextprotocol/server-filesystem\n/mi/directorio"}
                      value={argsInput}
                      onChange={e => setArgsInput(e.target.value)}
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-indigo-500"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-gray-300 mb-1">Variables de Entorno (KEY=VAL o JSON)</label>
                    <textarea
                      rows={2}
                      placeholder={"API_KEY=xyz\nDEBUG=true"}
                      value={envInput}
                      onChange={e => setEnvInput(e.target.value)}
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                </>
              ) : (
                <div>
                  <label className="block text-xs font-medium text-gray-300 mb-1">URL de SSE</label>
                  <input
                    type="url"
                    placeholder="http://localhost:8000/sse"
                    value={url}
                    onChange={e => setUrl(e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-indigo-500"
                  />
                </div>
              )}

              {/* Test result display */}
              {testResult && (
                <div className={`p-3 rounded-lg text-xs font-mono border ${
                  testResult.status === 'ok' 
                    ? 'bg-emerald-950/40 border-emerald-800 text-emerald-300' 
                    : 'bg-red-950/40 border-red-800 text-red-300'
                }`}>
                  {testResult.status === 'ok' ? '✓ Conexión exitosa' : `✗ ${testResult.message}`}
                  {testResult.tools && testResult.tools.length > 0 && (
                    <div className="mt-1">Herramientas: {testResult.tools.join(', ')}</div>
                  )}
                </div>
              )}

              <div className="flex items-center justify-between pt-2">
                <button
                  type="button"
                  onClick={handleTestConnection}
                  disabled={isTesting}
                  className="flex items-center gap-2 px-3 py-2 bg-gray-800 hover:bg-gray-700 text-gray-200 text-xs font-medium rounded-lg border border-gray-700 transition-colors"
                >
                  {isTesting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5 text-indigo-400" />}
                  Probar Conexión
                </button>

                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setIsModalOpen(false)}
                    className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs font-medium rounded-lg transition-colors"
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium rounded-lg shadow-sm transition-colors"
                  >
                    Guardar Servidor
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
