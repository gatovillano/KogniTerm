export interface FormattedMessage {
  html: string;
  plainText: string;
}

export class MessageFormatter {
  // Formatear mensaje para mostrar en el chat
  public static formatMessage(content: string, role: string): FormattedMessage {
    const plainText = content;
    const html = this.markdownToHtml(content);
    
    return { html, plainText };
  }

  // Convertir markdown simple a HTML
  private static markdownToHtml(text: string): string {
    let html = text;
    
    // Escapar HTML básico
    html = html.replace(/&/g, '&amp;')
               .replace(/</g, '&lt;')
               .replace(/>/g, '&gt;');
    
    // Bloques de código
    html = html.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
      return `<pre><code>${this.escapeHtml(code.trim())}</code></pre>`;
    });
    
    // Código en línea
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    
    // Negrita
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    
    // Cursiva
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    
    // Saltos de línea
    html = html.replace(/\n/g, '<br>');
    
    return html;
  }

  // Escapar HTML (implementación manual sin DOM)
  private static escapeHtml(text: string): string {
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
  // Formatear ruta de archivo para mostrar
  public static formatFilePath(uri: string): string {
    try {
      const url = new URL(uri);
      const path = url.pathname;
      const fileName = path.split('/').pop() || path;
      return fileName;
    } catch {
      return uri;
    }
  }

  // Formatear tamaño de archivo
  public static formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  // Formatear número de línea
  public static formatLineNumber(line: number): string {
    return line.toString().padStart(3, ' ');
  }

  // Truncar texto
  public static truncate(text: string, maxLength: number): string {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
  }

  // Formatear duración
  public static formatDuration(seconds: number): string {
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
  }
}
