export interface Heartbeat {
    id: string;
    name: string;
    prompt: string;
    interval_seconds: number;
    enabled: boolean;
    session_id?: string | null;
    last_run?: string | null;
    last_status?: string | null;
    last_error?: string | null;
}
export interface HeartbeatLog {
    id: string;
    heartbeat_id: string;
    timestamp: string;
    status: 'success' | 'failure' | 'running';
    output?: string;
    error?: string;
}
//# sourceMappingURL=heartbeat.d.ts.map