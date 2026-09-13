import React, { useState } from 'react';
import { CheckCircle2, Circle, Clock, ChevronDown, ChevronUp, BarChart3 } from 'lucide-react';

export interface Task {
  task_index: number;
  status: string;
  description: string;
}

export interface AgentPlan {
  agent_name: string;
  tasks: Task[];
}

// Normalizador helper para transformar la estructura de data.data que envía el backend de KogniTerm
export function normalizeTaskPlans(raw: any): AgentPlan[] {
  if (!raw) return [];
  
  // Si ya es un array de { agent_name, tasks: [...] }
  if (Array.isArray(raw)) {
    return raw.map((plan: any) => ({
      agent_name: plan.agent_name || plan.agent || 'Agente',
      tasks: (plan.tasks || []).map((t: any, idx: number) => ({
        task_index: typeof t.task_index === 'number' ? t.task_index : idx,
        status: t.status || 'pending',
        description: typeof t.task === 'string' ? t.task : (t.description || t.task?.task || String(t.task || ''))
      }))
    }));
  }

  // Si es un objeto tipo mapa { "agent_name": [ { task, status }, ... ] }
  if (typeof raw === 'object') {
    // Caso especial: { "plans": [...] }
    if (Array.isArray(raw.plans)) {
      return normalizeTaskPlans(raw.plans);
    }

    return Object.entries(raw).map(([agentName, tasksList]) => {
      const list: any[] = Array.isArray(tasksList) ? tasksList : [];
      return {
        agent_name: agentName,
        tasks: list.map((t: any, idx: number) => {
          let desc = '';
          if (typeof t === 'string') {
            desc = t;
          } else if (t && typeof (t as any) === 'object') {
            const obj = t as any;
            desc = obj.description || obj.task || '';
            if (typeof desc === 'object') {
              const innerObj = desc as any;
              desc = innerObj.task || innerObj.description || JSON.stringify(innerObj);
            }
          }
          return {
            task_index: typeof t.task_index === 'number' ? t.task_index : idx,
            status: t.status || 'pending',
            description: desc || `Tarea ${idx + 1}`
          };
        })
      };
    });
  }

  return [];
}

interface TaskTrackerProps {
  plans: AgentPlan[];
  isDark?: boolean;
}

const statusConfig = {
  pending: { icon: Circle, color: 'text-amber-500', bg: 'bg-amber-500/10', label: 'Pendiente' },
  'in-progress': { icon: Clock, color: 'text-indigo-500', bg: 'bg-indigo-500/10', label: 'En progreso' },
  done: { icon: CheckCircle2, color: 'text-emerald-500', bg: 'bg-emerald-500/10', label: 'Completado' },
  failed: { icon: Circle, color: 'text-rose-500', bg: 'bg-rose-500/10', label: 'Fallido' }
};

export function TaskTracker({ plans: rawPlans, isDark = true }: TaskTrackerProps) {
  const plans = normalizeTaskPlans(rawPlans);
  const [expandedAgents, setExpandedAgents] = useState<Record<string, boolean>>({});

  const toggleAgent = (agentName: string) => {
    setExpandedAgents(prev => ({
      ...prev,
      [agentName]: !prev[agentName]
    }));
  };

  const getProgress = (tasks: Task[]) => {
    const total = tasks.length;
    const done = tasks.filter(t => t.status === 'done').length;
    const inProgress = tasks.filter(t => t.status === 'in-progress').length;
    const donePercent = total > 0 ? (done / total) * 100 : 0;
    return { total, done, inProgress, donePercent };
  };

  if (plans.length === 0) {
    return (
      <div className="p-6 text-center opacity-50">
        <BarChart3 className="w-8 h-8 mx-auto mb-2" />
        <p className="text-sm">No hay planes de trabajo activos</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {plans.map(plan => {
        const progress = getProgress(plan.tasks);
        const isExpanded = expandedAgents[plan.agent_name] ?? true;

        return (
          <div key={plan.agent_name} className="chat-card rounded-xl overflow-hidden border border-inherit">
            {/* Header */}
            <div 
              onClick={() => toggleAgent(plan.agent_name)}
              className={`flex items-center justify-between p-4 cursor-pointer transition-colors ${isDark ? 'hover:bg-black/20' : 'hover:bg-black/5'}`}
            >
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400">
                  <BarChart3 className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-semibold text-sm">{plan.agent_name}</h3>
                  <p className={`text-xs ${isDark ? 'opacity-60' : 'opacity-65'}`}>
                    {progress.done} de {progress.total} tareas completadas
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                {/* Progress Bar */}
                <div className="flex items-center gap-2 min-w-[120px]">
                  <div className={`flex-1 h-2 rounded-full overflow-hidden ${isDark ? 'bg-black/40' : 'bg-slate-300/50'}`}>
                    <div 
                      className="h-full bg-gradient-to-r from-indigo-500 to-emerald-500 transition-all duration-300"
                      style={{ width: `${progress.donePercent}%` }}
                    />
                  </div>
                  <span className="text-xs font-mono opacity-70">{Math.round(progress.donePercent)}%</span>
                </div>

                {isExpanded ? (
                  <ChevronUp className="w-4 h-4 opacity-60" />
                ) : (
                  <ChevronDown className="w-4 h-4 opacity-60" />
                )}
              </div>
            </div>

            {/* Tasks List */}
            {isExpanded && (
              <div className="border-t border-inherit">
                {plan.tasks.map((task, index) => {
                  const StatusIcon = statusConfig[task.status as keyof typeof statusConfig]?.icon || Circle;
                  const config = statusConfig[task.status as keyof typeof statusConfig] || statusConfig.pending;

                  return (
                    <div 
                      key={task.task_index}
                      className={`flex items-center gap-3 px-4 py-2.5 text-sm ${
                        index !== plan.tasks.length - 1 ? 'border-b border-inherit' : ''
                      }`}
                    >
                      <StatusIcon className={`w-4 h-4 shrink-0 ${config.color}`} />
                      <span className={`flex-1 ${task.status === 'pending' ? 'opacity-50' : ''}`}>
                        {task.description}
                      </span>
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-mono ${config.bg} ${config.color}`}>
                        {config.label}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}