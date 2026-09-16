import React from 'react';
import { ThreadItem } from '@kogniterm/types';
export interface SessionHistoryPanelProps {
    threads: ThreadItem[];
    currentThreadId: string;
    onSelectThread: (threadId: string) => void;
    onDeleteThread: (e: React.MouseEvent, threadId: string) => void;
    onNewSession: () => void;
}
export declare const SessionHistoryPanel: React.FC<SessionHistoryPanelProps>;
//# sourceMappingURL=SessionHistoryPanel.d.ts.map