import { For, Show, createMemo } from "solid-js";
import { tasksStore, TaskItem, TaskStatus } from "../lib/tasks";

export function TaskTrackerPanel(props: { tabId: string }) {
  const tabTasks = () => tasksStore.get(props.tabId);
  const tasks = () => tabTasks().tasks;
  const isOpen = () => tabTasks().isOpen;

  const stats = createMemo(() => {
    const list = tasks();
    const total = list.length;
    const done = list.filter((t) => t.status === "done").length;
    const inProgress = list.filter((t) => t.status === "in_progress").length;
    const failed = list.filter((t) => t.status === "failed").length;
    const pending = list.filter((t) => t.status === "pending").length;
    const percent = total > 0 ? Math.round((done / total) * 100) : 0;
    const activeTask = list.find((t) => t.status === "in_progress") || list.find((t) => t.status === "pending");

    return { total, done, inProgress, failed, pending, percent, activeTask };
  });

  function statusBadge(status: TaskStatus) {
    switch (status) {
      case "done":
        return {
          label: "Completada",
          bg: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
          icon: "✓",
        };
      case "in_progress":
        return {
          label: "En curso",
          bg: "bg-amber-500/20 text-amber-300 border-amber-500/40",
          icon: "⚡",
        };
      case "failed":
        return {
          label: "Fallida",
          bg: "bg-red-500/20 text-red-300 border-red-500/40",
          icon: "✕",
        };
      default:
        return {
          label: "Pendiente",
          bg: "bg-zinc-800/80 text-zinc-400 border-white/[0.06]",
          icon: "○",
        };
    }
  }

  return (
    <Show when={tasks().length > 0}>
      <div class="mb-2.5 w-full select-none rounded-2xl bg-zinc-900/90 hover:bg-zinc-900/95 border border-white/[0.08] hover:border-white/15 shadow-[0_8px_32px_rgba(0,0,0,0.55)] backdrop-blur-xl overflow-hidden transition-all duration-300">
        {/* ── Barra de cabecera / Disparador del despliegue ── */}
        <div
          onClick={() => tasksStore.toggleOpen(props.tabId)}
          class="flex items-center justify-between gap-3 px-3.5 py-2.5 cursor-pointer text-[12px] text-zinc-300 transition-colors hover:bg-white/[0.02]"
          title={isOpen() ? "Clic para plegar el panel de tareas" : "Clic para desplegar el panel de tareas"}
        >
          {/* Lado izquierdo */}
          <div class="flex items-center gap-2.5 min-w-0 flex-1">
            <Show
              when={stats().inProgress > 0}
              fallback={
                <Show
                  when={stats().done === stats().total && stats().total > 0}
                  fallback={<span class="text-zinc-400 text-[13px]">📋</span>}
                >
                  <span class="w-4 h-4 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-[10px] font-bold">
                    ✓
                  </span>
                </Show>
              }
            >
              <span class="relative flex h-2.5 w-2.5">
                <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
                <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-amber-500" />
              </span>
            </Show>

            <span class="font-medium text-white shrink-0 text-[12.5px] tracking-tight">
              Tareas ({stats().done}/{stats().total})
            </span>

            {/* Si está colapsado, mostramos el resumen de la tarea activa */}
            <Show when={!isOpen()}>
              <span class="text-zinc-500 hidden sm:inline">·</span>
              <Show
                when={stats().activeTask}
                fallback={<span class="text-zinc-400 truncate text-[11.5px] hidden sm:inline">Todas completadas</span>}
              >
                <span class="text-zinc-300 truncate font-normal text-[11.5px] hidden sm:inline">
                  {stats().inProgress > 0 ? "En curso: " : "Siguiente: "}
                  <span class="text-zinc-200 font-medium">{stats().activeTask?.text}</span>
                </span>
              </Show>
            </Show>

            {/* Si está expandido, mostramos insignias de estado */}
            <Show when={isOpen()}>
              <Show when={stats().inProgress > 0}>
                <span class="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30 shrink-0">
                  {stats().inProgress} en curso
                </span>
              </Show>
              <span class="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/[0.06] text-zinc-300 shrink-0 hidden sm:inline">
                {stats().done} de {stats().total} completadas
              </span>
            </Show>
          </div>

          {/* Lado derecho con progreso y chevron animado */}
          <div class="flex items-center gap-3 shrink-0">
            <div class="w-16 sm:w-24 h-1.5 bg-white/[0.08] rounded-full overflow-hidden">
              <div
                class="h-full bg-gradient-to-r from-amber-400 to-emerald-400 transition-all duration-500 ease-out"
                style={{ width: `${stats().percent}%` }}
              />
            </div>

            <span class="text-[11px] font-mono text-zinc-400 shrink-0">
              {stats().percent}%
            </span>

            <button
              type="button"
              class={`w-6 h-6 rounded-lg flex items-center justify-center text-zinc-400 hover:text-white transition-all duration-300 transform ${
                isOpen() ? "rotate-180 bg-white/[0.08] text-white" : "rotate-0 hover:bg-white/[0.04]"
              }`}
              aria-label={isOpen() ? "Plegar tareas" : "Desplegar tareas"}
            >
              <svg class="w-3.5 h-3.5 fill-current" viewBox="0 0 20 20">
                <path
                  fill-rule="evenodd"
                  d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
                  clip-rule="evenodd"
                />
              </svg>
            </button>
          </div>
        </div>

        {/* ── Cuerpo desplegable con animación suave de acordeón ── */}
        <div class={`task-drawer-grid ${isOpen() ? "is-expanded" : "is-collapsed"}`}>
          <div class="overflow-hidden min-h-0">
            <div class="border-t border-white/[0.06] p-2.5 space-y-1.5 max-h-56 overflow-y-auto">
              <For each={tasks()}>
                {(task: TaskItem) => {
                  const badge = () => statusBadge(task.status);
                  return (
                    <div
                      class={`flex items-start justify-between gap-2.5 px-3 py-2 rounded-xl border transition-all duration-300 ${
                        task.status === "in_progress"
                          ? "bg-amber-500/[0.07] border-amber-500/30 shadow-[0_0_12px_rgba(245,158,11,0.08)]"
                          : task.status === "done"
                          ? "bg-white/[0.02] border-white/[0.04] opacity-80"
                          : "bg-white/[0.01] border-white/[0.04] hover:bg-white/[0.03]"
                      }`}
                    >
                      <div class="flex items-start gap-2.5 min-w-0 flex-1">
                        <span
                          class={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px] font-bold transition-colors duration-300 ${
                            task.status === "done"
                              ? "bg-emerald-500/20 text-emerald-400"
                              : task.status === "in_progress"
                              ? "bg-amber-500/25 text-amber-300 animate-pulse"
                              : task.status === "failed"
                              ? "bg-red-500/20 text-red-300"
                              : "border border-zinc-600 text-zinc-500"
                          }`}
                        >
                          {badge().icon}
                        </span>

                        <div class="min-w-0 flex-1">
                          <p
                            class={`text-[12.5px] leading-snug break-words transition-colors duration-200 ${
                              task.status === "done"
                                ? "text-zinc-400 line-through"
                                : task.status === "in_progress"
                                ? "text-white font-medium"
                                : "text-zinc-300"
                            }`}
                          >
                            {task.text}
                          </p>

                          <Show when={task.agent}>
                            <span class="inline-block mt-1 text-[9.5px] uppercase font-mono px-1.5 py-0.2 rounded bg-white/[0.05] text-zinc-400">
                              @{task.agent}
                            </span>
                          </Show>
                        </div>
                      </div>

                      <span
                        class={`shrink-0 text-[10px] font-medium px-2 py-0.5 rounded-full border transition-all duration-300 ${badge().bg}`}
                      >
                        {badge().label}
                      </span>
                    </div>
                  );
                }}
              </For>
            </div>
          </div>
        </div>
      </div>
    </Show>
  );
}
