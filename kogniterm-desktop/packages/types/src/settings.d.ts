export interface McpServerConfig {
    command?: string;
    args?: string[];
    env?: Record<string, string>;
    url?: string;
    type?: 'stdio' | 'sse' | 'http';
}
export interface KogniTermConfig {
    auto_approve?: boolean;
    theme?: 'light' | 'dark' | 'system';
    model?: string;
    provider?: string;
    api_key?: string;
    custom_instructions?: string;
    mcp_servers?: Record<string, McpServerConfig>;
    heartbeat_enabled?: boolean;
}
//# sourceMappingURL=settings.d.ts.map