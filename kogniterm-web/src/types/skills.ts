export interface ToolInfo {
  name: string;
  description: string;
}

export interface SkillInfo {
  name: string;
  version: string;
  author: string;
  description: string;
  category: string;
  scope: 'default' | 'agent' | 'global' | 'workspace' | 'external';
  path: string;
  security_level: 'low' | 'standard' | 'medium' | 'high' | 'elevated';
  tags: string[];
  dependencies: string[];
  tools: ToolInfo[];
  loaded: boolean;
}
