import { QuestionRequest } from '@kogniterm/types';
export interface QuestionModalProps {
    request: QuestionRequest | null;
    onRespond: (id: string, selected: string) => void;
    onCancel?: (id: string) => void;
}
export declare const QuestionModal: React.FC<QuestionModalProps>;
//# sourceMappingURL=QuestionModal.d.ts.map