// Type definitions for rich chat messages

export interface BaseMessage {
  id: string;
  sender: 'user' | 'assistant' | 'system' | 'tool';
  timestamp: string;
}

export interface TextMessage extends BaseMessage {
  type: 'text';
  text: string;
  reasoning?: string;
  agent?: string;
}

export interface DiffMessage extends BaseMessage {
  type: 'diff';
  filePath: string;
  toolName?: string;
  additions: number;
  deletions: number;
  diffContent: string;
  status: 'pending' | 'approved' | 'rejected';
  tool_call_id?: string;
}

export interface CommandMessage extends BaseMessage {
  type: 'command';
  command: string;
  output?: string;
  error?: string;
  exitCode?: number;
  status: 'pending' | 'running' | 'completed' | 'failed';
  tool_call_id?: string;
}

export interface ApprovalRequest extends BaseMessage {
  type: 'approval_request';
  action: 'edit' | 'command' | 'other';
  title: string;
  description: string;
  content: string;
  tool_call_id: string;
  status: 'pending' | 'approved' | 'rejected';
}

export interface TerminalMessage extends BaseMessage {
  type: 'terminal';
  session_id: string;
  output: string;
  interactive: boolean;
  status: 'idle' | 'running' | 'completed';
}

export type ChatMessage = TextMessage | DiffMessage | CommandMessage | ApprovalRequest | TerminalMessage;