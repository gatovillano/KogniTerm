import datetime

with open('/home/gato/Proyectos/Gemini-Interpreter/docs/Cambios.md', 'a') as f:
    f.write('\n\n## ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '\n\n')
    f.write('### Solución a caída de renderizado en React por objetos anidados\n')
    f.write('- Se previno el error `Objects are not valid as a React child` en la aplicación React (`kogniterm-desktop/apps/desktop/src/components/chat/ChatMessage.tsx`).\n')
    f.write('- Se introdujo una comprobación de tipo para `message.content` y `message.reasoning`. Si el contenido llega en formato de objeto (como en salidas JSON directas del LLM como `key_themes`), ahora se convierte a un string mediante `JSON.stringify()` antes de ser procesado por `ReactMarkdown`.\n')
