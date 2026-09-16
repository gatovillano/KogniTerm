export interface ToolCall {
    id: string;
    name: string;
    args: Record<string, unknown> | any;
}
export interface ToolResult {
    tool_call_id: string;
    content: string;
    is_error?: boolean;
}
export interface Message {
    id: string;
    role: 'user' | 'assistant' | 'system' | 'tool';
    content: string;
    images?: string[];
    reasoning?: string;
    tool_calls?: ToolCall[];
    tool_call_id?: string;
    timestamp: number;
}
export interface AppliedDiff {
    id: string;
    filePath: string;
    toolName?: string;
    diffContent: string;
    additions: number;
    deletions: number;
    timestamp: number;
}
export interface ChatState {
    messages: Message[];
    isGenerating: boolean;
    error: string | null;
}
export interface ApprovalRequest {
    id: string;
    message: string;
    title: string;
    diff_content?: string;
    file_path?: string;
    timestamp: number;
}
export interface QuestionOption {
    label: string;
    value: string;
    description?: string;
}
export interface QuestionRequest {
    id: string;
    question: string;
    options: string[];
    title?: string;
    details?: string;
    allow_freeform?: boolean;
    timestamp: number;
}
export interface TaskItem {
    id?: string;
    task: string;
    status: 'pending' | 'in-progress' | 'done' | 'failed';
    agent?: string;
}
export type TaskPlans = Record<string, TaskItem[]>;
export interface TerminalEntry {
    id: string;
    tool?: string;
    command?: string;
    output?: string;
    timestamp: number;
    type?: 'command' | 'output' | 'error' | 'info';
    content?: string;
    exitCode?: number;
}
//# sourceMappingURL=chat.d.ts.map