// KogniTerm Chat Panel - WebView Script
(function() {
  'use strict';

  const vscode = acquireVsCodeApi();

  const messagesContainer = document.getElementById('messages');
  const messageInput = document.getElementById('message-input');
  const sendButton = document.getElementById('send-button');

  let isWaitingForResponse = false;

  // Enviar mensaje
  function sendMessage() {
    const text = messageInput.value.trim();
    if (!text || isWaitingForResponse) return;

    // Enviar a la extensión
    vscode.postMessage({
      command: 'sendMessage',
      text: text
    });

    messageInput.value = '';
    messageInput.style.height = 'auto';
    isWaitingForResponse = false;
    updateSendButton();
  }

  // Actualizar estado del botón de envío
  function updateSendButton() {
    sendButton.disabled = isWaitingForResponse || !messageInput.value.trim();
  }

  // Helper para parsear Markdown
  function renderMarkdown(text) {
    if (!text) return '';
    if (window.marked && typeof window.marked.parse === 'function') {
      try {
        return window.marked.parse(text);
      } catch (e) {
        console.error('Error rendering markdown:', e);
      }
    }
    return escapeHtml(text);
  }

  // Actualizar Task Tracker UI
  function updateTaskTracker(tasksData) {
    const container = document.getElementById('task-tracker-container');
    const badge = document.getElementById('task-progress-badge');
    const taskList = document.getElementById('task-list');

    if (!tasksData || !container || !taskList) return;

    let tasks = [];
    if (Array.isArray(tasksData)) {
      tasks = tasksData;
    } else if (tasksData.tasks && Array.isArray(tasksData.tasks)) {
      tasks = tasksData.tasks;
    }

    if (tasks.length === 0) {
      container.style.display = 'none';
      return;
    }

    container.style.display = 'block';

    const completed = tasks.filter(t => t.status === 'done' || t.status === 'completed').length;
    if (badge) {
      badge.textContent = `${completed}/${tasks.length}`;
    }

    taskList.innerHTML = '';
    tasks.forEach(t => {
      const item = document.createElement('div');
      const isDone = t.status === 'done' || t.status === 'completed';
      const isInProgress = t.status === 'in_progress' || t.status === 'in-progress';
      
      item.className = `task-item ${isDone ? 'done' : ''}`;
      
      const icon = isDone ? '✅' : (isInProgress ? '⏳' : '⭕');
      item.innerHTML = `<span class="task-icon">${icon}</span><span>${escapeHtml(t.description || t.task || '')}</span>`;
      taskList.appendChild(item);
    });
  }

  // Agregar mensaje al contenedor
  function addMessage(message) {
    const messageEl = document.createElement('div');
    messageEl.className = `message ${message.role}`;
    
    const timestamp = new Date(message.timestamp).toLocaleTimeString();
    
    let headerHtml = '';
    if (message.role !== 'system') {
      const roleLabel = message.role === 'user' ? 'Tú' : 
                       message.role === 'assistant' ? 'KogniTerm' : 
                       message.role === 'tool' ? 'Herramienta' : 'Pensando';
      headerHtml = `<div class="message-header">
        <span>${roleLabel}</span>
        <span>${timestamp}</span>
      </div>`;
    }

    let contentHtml = '';

    // 1. Mensaje de Pensamiento (Desplegable y por defecto retraído)
    if (message.role === 'thinking') {
      contentHtml = `
        <details class="thinking-details">
          <summary>🧠 Pensando...</summary>
          <div class="thinking-content">${escapeHtml(message.content)}</div>
        </details>
      `;
    } 
    // 2. Mensaje de Herramientas (Tarjeta visual de herramienta)
    else if (message.role === 'tool' || message.toolName) {
      const toolName = message.toolName || 'Herramienta';
      contentHtml = `
        <div class="tool-card">
          <div class="tool-card-header">
            <span>🛠️ ${escapeHtml(toolName)}</span>
            ${message.skill ? `<span style="opacity: 0.8; font-size: 10px;">Skill: ${escapeHtml(message.skill)}</span>` : ''}
          </div>
          <div class="tool-card-body">${renderMarkdown(message.content)}</div>
        </div>
      `;
    } 
    // 3. Mensajes de Asistente y Usuario (Markdown Renderizado)
    else {
      let thinkingBlock = '';
      if (message.thinking) {
        thinkingBlock = `
          <details class="thinking-details">
            <summary>🧠 Pensando (finalizado)</summary>
            <div class="thinking-content">${escapeHtml(message.thinking)}</div>
          </details>
        `;
      }
      const renderedBody = message.role === 'user' ? escapeHtml(message.content) : renderMarkdown(message.content);
      contentHtml = `${thinkingBlock}<div class="message-content">${renderedBody}</div>`;
    }

    messageEl.innerHTML = headerHtml + contentHtml;
    messagesContainer.appendChild(messageEl);
    scrollToBottom();
  }

  // Actualizar último mensaje (para streaming en Markdown)
  function updateLastMessage(message) {
    if (!message) return;
    
    const messages = messagesContainer.querySelectorAll('.message.assistant');
    const lastMessage = messages[messages.length - 1];
    
    if (lastMessage) {
      const contentEl = lastMessage.querySelector('.message-content');
      if (contentEl) {
        let content = renderMarkdown(message.content || '');
        
        if (message.thinking) {
          content = `
            <details class="thinking-details">
              <summary>🧠 Pensando...</summary>
              <div class="thinking-content">${escapeHtml(message.thinking)}</div>
            </details>
            <div class="message-content">${content}</div>
          `;
          lastMessage.innerHTML = content;
        } else {
          contentEl.innerHTML = content;
        }
      }
      scrollToBottom();
    }
  }

  // Actualizar último mensaje de pensamiento (pensando en vivo)
  function updateLastThinkingMessage(message) {
    if (!message) return;
    const messages = messagesContainer.querySelectorAll('.message.thinking');
    const lastMessage = messages[messages.length - 1];
    if (lastMessage) {
      const thinkingContent = lastMessage.querySelector('.thinking-content');
      if (thinkingContent) {
        thinkingContent.textContent = message.content || '';
      }
      scrollToBottom();
    }
  }

  // Limpiar chat
  function clearChat() {
    messagesContainer.innerHTML = '';
    const container = document.getElementById('task-tracker-container');
    if (container) container.style.display = 'none';
  }

  // Actualizar ID de sesión
  function updateSession(sessionId) {
    console.log('Session ID:', sessionId);
  }

  // Scroll al final
  function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }

  // Escapar HTML
  function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // Auto-resize textarea
  messageInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 120) + 'px';
    updateSendButton();
  });

  // Enviar con Enter (Shift+Enter para nueva línea)
  messageInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // Botón de envío
  sendButton.addEventListener('click', sendMessage);

  // Escuchar mensajes desde la extensión
  window.addEventListener('message', event => {
    const message = event.data;
    
    switch (message.command) {
      case 'addMessage':
        addMessage(message.message);
        break;
      case 'updateLastThinkingMessage':
        updateLastThinkingMessage(message.message);
        break;
      case 'updateLastMessage':
        updateLastMessage(message.message);
        break;
      case 'updateTaskTracker':
        updateTaskTracker(message.tasks);
        break;
      case 'clear':
        clearChat();
        break;
      case 'updateSession':
        updateSession(message.sessionId);
        break;
    }
  });

  // Inicializar
  updateSendButton();
  addMessage({
    role: 'system',
    content: 'KogniTerm listo. Conecta al servidor para comenzar.',
    timestamp: new Date().toISOString()
  });
})();
