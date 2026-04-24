---
name: call_agents_parallel
version: 1.0.0
description: Invoca a Deep Coder y Deep Researcher en paralelo para tareas simultáneas
---

Esta herramienta te permite invocar dos agentes expertos (DeepCoder para edición de código y acciones técnicas, y DeepResearcher para investigación y lectura de contexto) de forma simultánea.

La TUI dividirá el panel inferior en dos columnas para visualizar el streaming de razonamiento y output de cada agente en paralelo.
Úsalo cuando necesitas acelerar el proceso delegando la lectura/investigación a un agente mientra el otro comienza la preparación del código u otras tareas.

### Uso
No requiere intervención especial, el TUI redireccionará dinámicamente el output al respectivo widget de la terminal.
