import { AppliedDiff } from './chat';

export function cleanAnsiAndRichFormatting(text: string): string {
  if (!text) return '';
  return text
    .replace(/(?:\x1b|\u001b)\[[0-9;]*[a-zA-Z]/g, '')
    .replace(/\[\d+(?:;\d+)*m/g, '')
    .replace(/\[\/?(dim|italic|bold|reverse|underline|cyan|red|green|yellow|blue|magenta|white|black)(?:\s+[a-z0-9_#-]+)*\]|\[\/\]/gi, '');
}

export function parseAppliedDiff(
  rawContent: string,
  fallbackFilePath?: string,
  toolName?: string
): AppliedDiff | null {
  if (!rawContent || typeof rawContent !== 'string') return null;

  let diffText = cleanAnsiAndRichFormatting(rawContent);
  let filePath = fallbackFilePath || '';
  let extractedTool = toolName || '';

  // 1. JSON Payload format
  const trimmedRaw = diffText.trim();
  if (trimmedRaw.startsWith('{') && trimmedRaw.endsWith('}')) {
    try {
      const parsed = JSON.parse(trimmedRaw);
      if (parsed.diff_content) diffText = cleanAnsiAndRichFormatting(parsed.diff_content);
      else if (parsed.diff) diffText = cleanAnsiAndRichFormatting(parsed.diff);
      if (parsed.file_path || parsed.filePath) filePath = parsed.file_path || parsed.filePath;
      if (parsed.tool || parsed.tool_name || parsed.operation) {
        extractedTool = parsed.tool || parsed.tool_name || parsed.operation;
      }
    } catch {
      // Ignore parse errors
    }
  }

  // Handle Rich Panel title & header extraction
  const titleMatch =
    diffText.match(/✅\s*Diff aplicado:\s*([^\n╭╮╰╯│]+)/i) ||
    diffText.match(/✅\s*Cambios aplicados en\s*`?([^`\n╭╮╰╯│]+)`?/i);
  if (titleMatch && !filePath) {
    filePath = titleMatch[1].trim();
  }

  const opLineMatch = diffText.match(/Operación:\s*`?([a-zA-Z0-9_\-]+)`?\s*/i);
  if (opLineMatch && !extractedTool) {
    extractedTool = opLineMatch[1];
  }

  // 2. Explicit ```diff ... ``` code block format
  const explicitDiffBlockMatch = diffText.match(/```diff\n([\s\S]*?)\n```/i);
  let isExplicitDiffBlock = false;
  if (explicitDiffBlockMatch) {
    isExplicitDiffBlock = true;
    const headerText = diffText.substring(0, diffText.indexOf('```'));
    const opMatch = headerText.match(/Operación:\s*`?([a-zA-Z0-9_\-]+)`?/i);
    if (opMatch && !extractedTool) extractedTool = opMatch[1];
    const pathMatch = headerText.match(/Cambios aplicados en\s*`?([^`\n]+)`?/i);
    if (pathMatch && !filePath) filePath = pathMatch[1];

    diffText = explicitDiffBlockMatch[1];
  }

  // Clean Rich Panel box borders & line numbers if present
  const rawLines = diffText.split('\n');
  const cleanedLines: string[] = [];

  for (let line of rawLines) {
    // Skip box border top/bottom lines (e.g. ╭──────╮ or ╰──────╯)
    if (/^[╭╰]\s*─+.*[╮╯]$/.test(line.trim()) || /^─+$/.test(line.trim())) {
      continue;
    }
    // Remove box border side characters '│'
    if (line.includes('│')) {
      line = line.replace(/^\s*│\s*/, '').replace(/\s*│\s*$/, '');
    }

    // If line has Rich diff table line numbers before +, -, or @@:
    // e.g. " 166 166 # etc." or " 166 - (0.0...)" or " 166+ (0.0...)"
    if (/^\s*\d*(?:\s+\d+)?\s*[\+\-\@\ ]/.test(line)) {
      line = line.replace(/^\s*\d+(?:\s+\d+)?\s*(?=[\+\-\@\ ])/, '');
    }

    cleanedLines.push(line);
  }

  diffText = cleanedLines.join('\n');

  // 3. Strict validation: MUST have valid unified diff header markers or explicit ```diff block
  const hasHeaderLines =
    /--- (a\/|\/|[^\s]+)[\s\S]*?\+\+\+ (b\/|\/|[^\s]+)/.test(diffText) ||
    /diff --git a\//.test(diffText) ||
    /Index:\s+/.test(diffText);
  const hasHunkHeader = /^@@\s+-\d+(?:,\d+)?\s+\+\d+(?:,\d+)?\s+@@/m.test(diffText);

  if (!hasHeaderLines && !hasHunkHeader && !isExplicitDiffBlock) {
    return null;
  }

  // Extract file path from unified diff headers if not already set
  if (!filePath) {
    const pathMatch =
      diffText.match(/\+\+\+\s+(?:b\/)?([^\s\n]+)/) ||
      diffText.match(/---\s+(?:a\/)?([^\s\n]+)/);
    if (pathMatch && pathMatch[1] !== '/dev/null' && pathMatch[1] !== 'a' && pathMatch[1] !== 'b') {
      filePath = pathMatch[1];
    }
  }

  // 4. Parse diff lines & count additions/deletions accurately
  const lines = diffText.split('\n');
  let additions = 0;
  let deletions = 0;
  let inHunk = false;

  for (const line of lines) {
    const trimmed = line.trim();

    if (trimmed.startsWith('@@')) {
      inHunk = true;
      continue;
    }

    if (
      line.includes('--- ') ||
      line.includes('+++ ') ||
      line.includes('Index:') ||
      line.includes('diff --git')
    ) {
      inHunk = true;
      continue;
    }

    if (inHunk || isExplicitDiffBlock) {
      if (line.startsWith('+') && !line.startsWith('+++')) {
        additions++;
      } else if (line.startsWith('-') && !line.startsWith('---')) {
        deletions++;
      }
    }
  }

  return {
    id: `diff-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    filePath: filePath || 'Archivo modificado',
    toolName: extractedTool,
    diffContent: diffText,
    additions,
    deletions,
    timestamp: Date.now(),
  };
}
