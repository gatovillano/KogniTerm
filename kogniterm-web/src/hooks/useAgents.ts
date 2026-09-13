import { useState, useEffect } from 'react';

interface Agent {
  id: string;
  name: string;
  role: string;
  description: string;
  model: string;
  icon: string;
  is_custom: boolean;
}

interface UseAgentsReturn {
  agents: Agent[];
  loading: boolean;
  fetchAgents: () => Promise<void>;
  createCustomAgent: (data: {
    name: string;
    role: string;
    description: string;
    model: string;
    config: any;
  }) => Promise<boolean>;
}

export function useAgents(): UseAgentsReturn {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchAgents = async () => {
    try {
      const res = await fetch('/api/agents');
      if (res.ok) {
        const data = await res.json();
        setAgents(data.agents || []);
      }
    } catch (err) {
      console.error('Error al cargar agentes:', err);
    } finally {
      setLoading(false);
    }
  };

  const createCustomAgent = async (data: {
    name: string;
    role: string;
    description: string;
    model: string;
    config: any;
  }) => {
    try {
      const res = await fetch('/api/agents/custom', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      if (res.ok) {
        await fetchAgents(); // Recargar lista
        return true;
      }
      return false;
    } catch (err) {
      console.error('Error al crear agente:', err);
      return false;
    }
  };

  useEffect(() => {
    fetchAgents();
  }, []);

  return { agents, loading, fetchAgents, createCustomAgent };
}