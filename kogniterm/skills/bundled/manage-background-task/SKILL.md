---
name: manage-background-task
description: Consulta, monitorea y gestiona las tareas y comandos ejecutados en segundo plano.
tools:
  - name: manage_background_task
    description: Permite listar tareas activas/históricas en segundo plano, consultar estado/salida, o cancelar la ejecución.
---

# Manage Background Task

Esta herramienta permite a los agentes de KogniTerm interactuar con comandos que se están ejecutando de manera asíncrona en segundo plano.

## Acciones Disponibles:
- `action='list'`: Devuelve la lista de todas las tareas en segundo plano lanzadas en la sesión activa.
- `action='status'`: Muestra el estado (`running`, `completed`, `failed`, `killed`) y las últimas líneas de salida de la tarea indicada por `task_id`.
- `action='kill'`: Termina la ejecución de una tarea en segundo plano.
