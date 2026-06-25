import { CheckCircle2, Circle, Loader2, ListTodo } from 'lucide-react';

interface Task {
  task: string;
  status: string; // 'pending' | 'in-progress' | 'done'
}

interface TaskTrackerProps {
  taskPlans: Record<string, Task[]>;
}

export function TaskTracker({ taskPlans }: TaskTrackerProps) {
  // Solo mostramos si hay planes con tareas
  const hasTasks = Object.values(taskPlans).some((plan) => plan.length > 0);

  if (!hasTasks) {
    return null;
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'done':
        return <CheckCircle2 size={16} className="text-emerald-500" />;
      case 'in-progress':
        return <Loader2 size={16} className="text-indigo-400 animate-spin" />;
      case 'pending':
      default:
        return <Circle size={16} className="text-zinc-500" />;
    }
  };

  return (
    <div className="flex flex-col w-72 border-l border-zinc-800 bg-zinc-950/50 overflow-y-auto animate-slide-in-right">
      <div className="p-4 border-b border-zinc-800/50 sticky top-0 bg-zinc-950/80 backdrop-blur-md z-10 flex items-center gap-2">
        <ListTodo size={18} className="text-indigo-400" />
        <h3 className="font-medium text-sm text-zinc-200">Plan de Tareas</h3>
      </div>
      
      <div className="p-4 space-y-6">
        {Object.entries(taskPlans).map(([agentName, tasks]) => {
          if (tasks.length === 0) return null;
          
          const completed = tasks.filter(t => t.status === 'done').length;
          const total = tasks.length;
          const progress = Math.round((completed / total) * 100);

          return (
            <div key={agentName} className="space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                  {agentName.replace(/_/g, ' ')}
                </h4>
                <span className="text-[10px] text-zinc-500 font-medium">{progress}%</span>
              </div>
              
              <div className="h-1 w-full bg-zinc-900 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-indigo-500 transition-all duration-500 ease-out"
                  style={{ width: `${progress}%` }}
                />
              </div>

              <div className="space-y-2 mt-2">
                {tasks.map((task, idx) => (
                  <div 
                    key={idx} 
                    className={`flex items-start gap-3 p-2 rounded-lg text-sm transition-colors ${
                      task.status === 'in-progress' 
                        ? 'bg-indigo-500/10 border border-indigo-500/20' 
                        : 'hover:bg-zinc-800/50 border border-transparent'
                    }`}
                  >
                    <div className="mt-0.5 shrink-0">
                      {getStatusIcon(task.status)}
                    </div>
                    <span className={`leading-snug ${
                      task.status === 'done' 
                        ? 'text-zinc-500 line-through' 
                        : task.status === 'in-progress'
                          ? 'text-indigo-200'
                          : 'text-zinc-300'
                    }`}>
                      {task.task}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
