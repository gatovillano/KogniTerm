export interface ToolCall {
    id: string;
    name: string;
    args: any;
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
    reasoning?: string;
    tool_calls?: ToolCall[];
    tool_call_id?: string; // Para mensajes con rol 'tool'
    timestamp: number;
}

export interface ChatState {
    messages: Message[];
    isGenerating: boolean;
    error: string | null;
}
