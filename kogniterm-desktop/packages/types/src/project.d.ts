export interface Project {
    id: string;
    name: string;
    path: string;
    isExpanded: boolean;
    createdAt: string;
}
export interface ProjectItem {
    name: string;
    path: string;
    isDirectory: boolean;
    size?: number;
    children?: ProjectItem[];
}
//# sourceMappingURL=project.d.ts.map