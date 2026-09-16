export interface ThreadItem {
    id: string;
    title?: string;
    updated_at?: string;
    created_at?: string;
    message_count?: number;
    last_message?: string;
    workspaceDir?: string;
    workspace_dir?: string;
}
export interface SessionSummary {
    session_id: string;
    created_at: string;
    updated_at?: string;
    message_count: number;
    workspace_dir: string;
    title?: string;
}
//# sourceMappingURL=session.d.ts.map