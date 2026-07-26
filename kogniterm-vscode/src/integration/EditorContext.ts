import * as vscode from 'vscode';

export interface FileContext {
  uri: string;
  fileName: string;
  workspaceFolder: string;
  content: string;
  language: string;
  lineCount: number;
}

export interface SelectionContext {
  text: string;
  startLine: number;
  endLine: number;
  startColumn: number;
  endColumn: number;
}

export class EditorContext implements vscode.Disposable {
  private lastActiveFile: FileContext | null = null;
  private lastSelection: SelectionContext | null = null;
  private readonly _disposables: vscode.Disposable[] = [];

  constructor() {
    // Escuchar cambios en el editor activo
    this._disposables.push(
      vscode.window.onDidChangeActiveTextEditor((editor) => {
        if (editor) {
          this.lastActiveFile = this.getActiveFile();
        }
      })
    );

    // Escuchar cambios en la selección
    this._disposables.push(
      vscode.window.onDidChangeTextEditorSelection((event) => {
        if (event.textEditor === vscode.window.activeTextEditor) {
          this.lastSelection = this.getSelection();
        }
      })
    );
  }

  public dispose(): void {
    this._disposables.forEach(d => d.dispose());
    this._disposables.length = 0;
  }
  public getActiveFile(): FileContext | null {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      return null;
    }

    const document = editor.document;
    const workspaceFolder = this.getWorkspaceFolder(document.uri);
    
    const context: FileContext = {
      uri: document.uri.toString(),
      fileName: document.fileName,
      workspaceFolder: workspaceFolder || '',
      content: document.getText(),
      language: document.languageId,
      lineCount: document.lineCount
    };

    this.lastActiveFile = context;
    return context;
  }

  public getSelection(): SelectionContext | null {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.selection.isEmpty) {
      return null;
    }

    const selection = editor.selection;
    const text = editor.document.getText(selection);

    const context: SelectionContext = {
      text,
      startLine: selection.start.line + 1,
      endLine: selection.end.line + 1,
      startColumn: selection.start.character + 1,
      endColumn: selection.end.character + 1
    };

    this.lastSelection = context;
    return context;
  }

  public getLastActiveFile(): FileContext | null {
    return this.lastActiveFile;
  }

  public getLastSelection(): SelectionContext | null {
    return this.lastSelection;
  }

  public getWorkspaceFolders(): string[] {
    if (vscode.workspace.workspaceFolders) {
      return vscode.workspace.workspaceFolders.map(f => f.uri.fsPath);
    }
    return [];
  }

  public getWorkspaceRoot(): string | null {
    if (vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders.length > 0) {
      return vscode.workspace.workspaceFolders[0].uri.fsPath;
    }
    return null;
  }

  private getWorkspaceFolder(uri: vscode.Uri): string | null {
    if (vscode.workspace.workspaceFolders) {
      for (const folder of vscode.workspace.workspaceFolders) {
        if (uri.toString().startsWith(folder.uri.toString())) {
          return folder.uri.fsPath;
        }
      }
    }
    return null;
  }

  public async openFile(uri: string): Promise<boolean> {
    try {
      const document = await vscode.workspace.openTextDocument(uri);
      await vscode.window.showTextDocument(document);
      return true;
    } catch (error) {
      vscode.window.showErrorMessage(`KogniTerm: No se pudo abrir el archivo - ${error}`);
      return false;
    }
  }

  public async applyEdits(uri: string, edits: { range: vscode.Range; text: string }[]): Promise<boolean> {
    try {
      const document = await vscode.workspace.openTextDocument(uri);
      const workspaceEdit = new vscode.WorkspaceEdit();
      
      edits.forEach(edit => {
        workspaceEdit.replace(document.uri, edit.range, edit.text);
      });

      const success = await vscode.workspace.applyEdit(workspaceEdit);
      
      if (success) {
        await document.save();
        vscode.window.showInformationMessage('KogniTerm: Cambios aplicados correctamente');
      }
      
      return success;
    } catch (error) {
      vscode.window.showErrorMessage(`KogniTerm: Error al aplicar cambios - ${error}`);
      return false;
    }
  }

  public getDiff(original: string, modified: string): string {
    // Implementación simple de diff - en producción usar una librería como 'diff'
    const originalLines = original.split('\n');
    const modifiedLines = modified.split('\n');
    
    let diff = '';
    const maxLines = Math.max(originalLines.length, modifiedLines.length);
    
    for (let i = 0; i < maxLines; i++) {
      const originalLine = originalLines[i] || '';
      const modifiedLine = modifiedLines[i] || '';
      
      if (originalLine !== modifiedLine) {
        if (originalLine) {
          diff += `- ${originalLine}\n`;
        }
        if (modifiedLine) {
          diff += `+ ${modifiedLine}\n`;
        }
      }
    }
    
    return diff || 'Sin cambios';
  }
}
