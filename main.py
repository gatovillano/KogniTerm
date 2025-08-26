import asyncio
import json
import os
import sys

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from langgraph.graph import StateGraph
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig # Importar RunnableConfig

from kogniterm.core.agents.orchestrator_agent import OrchestratorState, orchestrator_app
from kogniterm.core.llm_service import llm_service
from kogniterm.core.tools.set_llm_instructions_tool import SetLLMInstructionsTool

app = FastAPI()
templates = Jinja2Templates(directory="templates") # Asumiendo que tienes una carpeta 'templates' en la raíz

# Inicializar el estado del orquestador para la sesión
# NOTA: En una aplicación real, esto debería ser manejado por sesión de usuario
# o por algún tipo de almacenamiento persistente.
session_state: OrchestratorState = OrchestratorState()

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "messages": []})

@app.post("/chat/")
async def chat_endpoint(request: Request):
    global session_state
    data = await request.json()
    user_message_content = data.get("message", "")

    # Manejar el comando %rules
    if user_message_content.startswith("%rules "):
        instructions = user_message_content[len("%rules "):].strip()
        print(f"Comando %rules detectado. Estableciendo instrucciones: {instructions}", file=sys.stdout, flush=True)
        # Aquí directamente actualizamos el custom_system_message en el estado de la sesión
        session_state.custom_system_message = instructions
        response_message = f"Reglas del LLM actualizadas a: '{instructions}'"
        session_state.messages.append(HumanMessage(content=user_message_content))
        session_state.messages.append(AIMessage(content=response_message))
        return {"response": response_message}
    elif user_message_content == "%rules":
        response_message = "Uso: %rules <tus_instrucciones>. Por ejemplo: %rules Responde siempre en español y con emojis."
        session_state.messages.append(HumanMessage(content=user_message_content))
        session_state.messages.append(AIMessage(content=response_message))
        return {"response": response_message}

    # Procesar con el orquestador
    session_state.user_query = user_message_content
    session_state.messages.append(HumanMessage(content=user_message_content))

    config: RunnableConfig = {"configurable": {"thread_id": "1"}}
    
    # Ejecutar el orquestador
    # Aquí es donde el orquestador toma el control y potencialmente usa custom_system_message
    final_state_dict = await orchestrator_app.ainvoke(session_state, config)
    # Convertir el diccionario de estado a un objeto OrchestratorState para facilitar el acceso a atributos
    final_state = OrchestratorState(**final_state_dict)

    # Limpiar el estado para la siguiente interacción si el orquestador ha terminado
    if final_state.status in ["finished", "failed"]:
        response_content = final_state.final_response
        # Reiniciar el estado del orquestador para la próxima interacción, manteniendo el custom_system_message
        new_session_state = OrchestratorState()
        new_session_state.custom_system_message = session_state.custom_system_message
        new_session_state.messages = session_state.messages # Mantener historial de mensajes
        session_state = new_session_state
    else:
        response_content = final_state.plan_presentation if final_state.plan_presentation else "Procesando..."

    return {"response": response_content}

@app.post("/approve/")
async def approve_plan(request: Request):
    global session_state
    data = await request.json()
    approval = data.get("approval")

    if approval == "s":
        session_state.user_approval = True
    else:
        session_state.user_approval = False
    
    config: RunnableConfig = {"configurable": {"thread_id": "1"}}
    final_state_dict = await orchestrator_app.ainvoke(session_state, config)
    final_state = OrchestratorState(**final_state_dict)

    response_content = final_state.final_response if final_state.final_response else "Plan procesado."
    
    # Limpiar el estado si el orquestador ha terminado
    if final_state.status in ["finished", "failed"]:
        new_session_state = OrchestratorState()
        new_session_state.custom_system_message = session_state.custom_system_message
        new_session_state.messages = session_state.messages
        session_state = new_session_state

    return {"response": response_content}

@app.post("/execute_command_response/")
async def execute_command_response(request: Request):
    global session_state
    data = await request.json()
    command_output = data.get("output")

    session_state.tool_output = command_output
    
    config: RunnableConfig = {"configurable": {"thread_id": "1"}}
    final_state_dict = await orchestrator_app.ainvoke(session_state, config)
    final_state = OrchestratorState(**final_state_dict)

    response_content = final_state.final_response if final_state.final_response else "Comando ejecutado."

    # Limpiar el estado si el orquestador ha terminado
    if final_state.status in ["finished", "failed"]:
        new_session_state = OrchestratorState()
        new_session_state.custom_system_message = session_state.custom_system_message
        new_session_state.messages = session_state.messages
        session_state = new_session_state

    return {"response": response_content}

# Esto es para que FastAPI sepa qué comando ejecutar en el terminal del usuario
@app.get("/action_needed/")
async def action_needed():
    global session_state
    if session_state.action_needed == "execute_command" and session_state.command_to_execute:
        command = session_state.command_to_execute
        session_state.command_to_execute = None # Limpiar después de enviar
        session_state.action_needed = None
        return {"action": "execute_command", "command": command}
    elif session_state.action_needed == "await_user_approval":
        session_state.action_needed = None
        return {"action": "await_user_approval"}
    elif session_state.action_needed == "final_response":
        response = session_state.final_response
        session_state.action_needed = None
        session_state.final_response = ""
        return {"action": "final_response", "response": response}
    return {"action": "none"}