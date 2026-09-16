import { ApprovalRequest } from '@kogniterm/types';
export interface CommandApprovalProps {
    request: ApprovalRequest;
    onApprove: (id: string) => void;
    onReject: (id: string) => void;
    isInline?: boolean;
}
export declare const CommandApproval: React.FC<CommandApprovalProps>;
//# sourceMappingURL=CommandApproval.d.ts.map