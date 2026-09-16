export function parseAppliedDiff(rawContent, fallbackFilePath, toolName) {
    if (!rawContent || typeof rawContent !== 'string')
        return null;
    let diffText = rawContent;
    let filePath = fallbackFilePath || '';
    let extractedTool = toolName || '';
    // 1. JSON Payload format
    if (rawContent.trim().startsWith('{') && rawContent.trim().endsWith('}')) {
        try {
            const parsed = JSON.parse(rawContent);
            if (parsed.diff_content)
                diffText = parsed.diff_content;
            else if (parsed.diff)
                diffText = parsed.diff;
            if (parsed.file_path || parsed.filePath)
                filePath = parsed.file_path || parsed.filePath;
            if (parsed.tool || parsed.tool_name || parsed.operation) {
                extractedTool = parsed.tool || parsed.tool_name || parsed.operation;
            }
        }
        catch {
            // Ignore parse errors
        }
    }
    // 2. Explicit ```diff ... ``` code block format
    const explicitDiffBlockMatch = diffText.match(/```diff\n([\s\S]*?)\n```/i);
    let isExplicitDiffBlock = false;
    if (explicitDiffBlockMatch) {
        isExplicitDiffBlock = true;
        const headerText = diffText.substring(0, diffText.indexOf('```'));
        const opMatch = headerText.match(/Operación:\s*`?([a-zA-Z0-9_\-]+)`?/i);
        if (opMatch && !extractedTool)
            extractedTool = opMatch[1];
        const pathMatch = headerText.match(/Cambios aplicados en\s*`?([^`\n]+)`?/i);
        if (pathMatch && !filePath)
            filePath = pathMatch[1];
        diffText = explicitDiffBlockMatch[1];
    }
    else {
        const opLineMatch = diffText.match(/Operación:\s*`?([a-zA-Z0-9_\-]+)`?\s*/i);
        if (opLineMatch) {
            if (!extractedTool)
                extractedTool = opLineMatch[1];
            diffText = diffText.replace(/Operación:\s*`?[a-zA-Z0-9_\-]+`?\s*/i, '');
        }
        const titleMatch = diffText.match(/✅\s*Diff aplicado:\s*([^\n]+)/i) ||
            diffText.match(/✅\s*Cambios aplicados en\s*`?([^`\n]+)`?/i);
        if (titleMatch && !filePath) {
            filePath = titleMatch[1].trim();
        }
    }
    // 3. Strict validation: MUST have valid unified diff header markers or explicit ```diff block
    const hasHeaderLines = /--- (a\/|\/|[^\s]+)[\s\S]*?\+\+\+ (b\/|\/|[^\s]+)/.test(diffText) ||
        /diff --git a\//.test(diffText) ||
        /Index:\s+/.test(diffText);
    const hasHunkHeader = /^@@\s+-\d+(?:,\d+)?\s+\+\d+(?:,\d+)?\s+@@/m.test(diffText);
    if (!hasHeaderLines && !hasHunkHeader && !isExplicitDiffBlock) {
        return null;
    }
    // Extract file path from unified diff headers if not already set
    if (!filePath) {
        const pathMatch = diffText.match(/\+\+\+\s+(?:b\/)?([^\s\n]+)/) ||
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
        if (line.includes('--- ') ||
            line.includes('+++ ') ||
            line.includes('Index:') ||
            line.includes('diff --git')) {
            inHunk = true;
            continue;
        }
        if (inHunk || isExplicitDiffBlock) {
            if (line.startsWith('+') && !line.startsWith('+++')) {
                additions++;
            }
            else if (line.startsWith('-') && !line.startsWith('---')) {
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
