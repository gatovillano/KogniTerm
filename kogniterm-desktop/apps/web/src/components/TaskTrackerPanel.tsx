import { For, Show, createMemo } from "solid-js";
import { tasksStore, TaskItem, TaskStatus } from "../lib/tasks";
import { IconBolt, IconCheck, IconChevronDown, IconClose, IconListChecks } from "./Icons";

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
        };
      case "in_progress":
        return {
          label: "En curso",
          bg: "bg-amber-500/15 text-amber-300 border-amber-500/35",
        };
      case "failed":
        return {
          label: "Fallida",
          bg: "bg-red-500/15 text-red-300 border-red-500/35",
        };
      default:
        return {
          label: "Pendiente",
          bg: "bg-[var(--kt-bg-hover)] text-[var(--kt-text-muted)] border-[var(--kt-border-subtle)]",
        };
    }
  }

  return (
    <Show when={tasks().length > 0}>
      <div class="mb-2.5 w-full select-none rounded-2xl kt-card overflow-hidden transition-all duration-200">
        {/* Cabecera */}
        <div
          onClick={() => tasksStore.toggleOpen(props.tabId)}
          class="flex items-center justify-between gap-3 px-3.5 py-2.5 cursor-pointer text-[12px] text-[var(--kt-text-secondary)] hover:bg-[var(--kt-bg-hover)] transition-colors"
          title={isOpen() ? "Clic para plegar el panel de tareas" : "Clic para desplegar el panel de tareas"}
        >
          <div class="flex items-center gap-2.5 min-w-0 flex-1">
            <Show
              when={stats().inProgress > 0}
              fallback={
                <Show
                  when={stats().done === stats().total && stats().total > 0}
                  fallback={<IconListChecks size={14} class="text-[var(--kt-text-muted)] shrink-0" />}
                >
                  <span class="w-4 h-4 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center shrink-0">
                    <IconCheck size={10} />
                  </span>
                </Show>
              }
            >
              <span class="relative flex h-2.5 w-2.5 shrink-0">
                <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
                <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-amber-500" />
              </span>
            </Show>

            <span class="font-semibold text-[var(--kt-text-primary)] shrink-0 text-[12.5px] tracking-tight tabular-nums">
              Tareas ({stats().done}/{stats().total})
            </span>

            <Show when={!isOpen()}>
              <span class="text-[var(--kt-text-faint)] hidden sm:inline">·</span>
              <Show
                when={stats().activeTask}
                fallback={
                  <span class="text-[var(--kt-text-muted)] truncate text-[11.5px] hidden sm:inline">
                    Todas completadas
                  </span>
                }
              >
                <span class="text-[var(--kt-text-muted)] truncate font-normal text-[11.5px] hidden sm:inline">
                  {stats().inProgress > 0 ? "En curso: " : "Siguiente: "}
                  <span class="text-[var(--kt-text-primary)] font-medium">{stats().activeTask?.text}</span>
                </span>
              </Show>
            </Show>

            <Show when={isOpen()}>
              <Show when={stats().inProgress > 0}>
                <span class="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30 shrink-0">
                  {stats().inProgress} en curso
                </span>
              </Show>
              <span class="text-[10px] font-mono px-2 py-0.5 rounded-full bg-[var(--kt-bg-hover)] text-[var(--kt-text-muted)] shrink-0 hidden sm:inline">
                {stats().done} de {stats().total} completadas
              </span>
            </Show>
          </div>

          <div class="flex items-center gap-3 shrink-0">
            <div class="w-16 sm:w-24 h-1.5 bg-[var(--kt-bg-active)] rounded-full overflow-hidden">
              <div
                class="h-full bg-gradient-to-r from-amber-400 to-emerald-400 transition-all duration-500 ease-out"
                style={{ width: `${stats().percent}%` }}
              />
            </div>

            <span class="text-[11px] font-mono text-[var(--kt-text-muted)] shrink-0 tabular-nums">
              {stats().percent}%
            </span>

            <button
              type="button"
              class={`w-6 h-6 rounded-lg flex items-center justify-center text-[var(--kt-text-muted)] hover:text-[var(--kt-text-primary)] transition-all duration-200 transform ${
                isOpen() ? "rotate-180 bg-[var(--kt-bg-active)] text-[var(--kt-text-primary)]" : "rotate-0"
              }`}
              aria-label={isOpen() ? "Plegar tareas" : "Desplegar tareas"}
            >
              <IconChevronDown size={14} />
            </button>
          </div>
        </div>

        {/* Lista desplegable */}
        <div class={`task-drawer-grid ${isOpen() ? "is-expanded" : "is-collapsed"}`}>
          <div class="overflow-hidden min-h-0">
            <div class="border-t border-[var(--kt-border-subtle)] p-2.5 space-y-1.5 max-h-56 overflow-y-auto">
              <For each={tasks()}>
                {(task: TaskItem) => {
                  const badge = () => statusBadge(task.status);
                  return (
                    <div
                      class={`flex items-start justify-between gap-2.5 px-3 py-2 rounded-xl border transition-all duration-200 ${
                        task.status === "in_progress"
                          ? "bg-amber-500/[0.08] border-amber-500/30"
                          : task.status === "done"
                            ? "bg-[var(--kt-bg-hover)] border-transparent opacity-75"
                            : "bg-transparent border-[var(--kt-border-subtle)]"
                      }`}
                    >
                      <div class="flex items-start gap-2.5 min-w-0 flex-1">
                        <span
                          class={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full transition-colors ${
                            task.status === "done"
                              ? "bg-emerald-500/20 text-emerald-400"
                              : task.status === "in_progress"
                                ? "bg-amber-500/25 text-amber-300 animate-pulse"
                                : task.status === "failed"
                                  ? "bg-red-500/20 text-red-300"
                                  : "border border-[var(--kt-border-strong)]"
                          }`}
                        >
                          <Show when={task.status === "done"}>
                            <IconCheck size={10} />
                          </Show>
                          <Show when={task.status === "in_progress"}>
                            <IconBolt size={10} />
                          </Show>
                          <Show when={task.status === "failed"}>
                            <IconClose size={10} />
                          </Show>
                        </span>

                        <div class="min-w-0 flex-1">
                          <p
                            class={`text-[12.5px] leading-snug break-words transition-colors ${
                              task.status === "done"
                                ? "text-[var(--kt-text-muted)] line-through"
                                : task.status === "in_progress"
                                  ? "text-[var(--kt-text-primary)] font-medium"
                                  : "text-[var(--kt-text-secondary)]"
                            }`}
                          >
                            {task.text}
                          </p>

                          <Show when={task.agent}>
                            <span class="inline-block mt-1 text-[10px] font-mono px-1.5 py-0.5 rounded bg-[var(--kt-bg-hover)] text-[var(--kt-text-muted)]">
                              @{task.agent}
                            </span>
                          </Show>
                        </div>
                      </div>

                      <span
                        class={`shrink-0 text-[10px] font-medium px-2 py-0.5 rounded-full border ${badge().bg}`}
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
