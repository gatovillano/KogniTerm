from dataclasses import dataclass
from typing import List, Optional, Dict
import difflib
import os
from rich.console import Console
from rich.text import Text
from rich.syntax import Syntax
from rich.table import Table
from rich.style import Style

@dataclass
class DiffLine:
    type: str  # 'add', 'del', 'context', 'hunk'
    content: str
    old_line: Optional[int] = None
    new_line: Optional[int] = None

class DiffRenderer:
    def __init__(self, theme_colors: Optional[Dict[str, str]] = None):
        self.theme_colors = theme_colors or {
            'diff_add_color': 'green',
            'diff_delete_color': 'red',
            'diff_context_color': 'grey50',
            'diff_hunk_header_color': 'blue',
            'line_number_color': 'dim cyan'
        }
        self.console = Console()
        # Habilitar fondos de color para mejor visibilidad
        self.use_backgrounds = True

    def _infer_language(self, file_path: str) -> str:
        ext = os.path.splitext(file_path)[1].lower()
        # Mapeo de extensiones a nombres de lenguajes para pygments
        language_map = {
            '.py': 'python', '.js': 'javascript', '.ts': 'typescript', '.tsx': 'typescript',
            '.html': 'html', '.css': 'css', '.md': 'markdown',
            '.sh': 'bash', '.json': 'json', '.yaml': 'yaml', '.yml': 'yaml',
            '.java': 'java', '.c': 'c', '.cpp': 'cpp', '.rb': 'ruby',
            '.go': 'go', '.rs': 'rust', '.php': 'php', '.sql': 'sql',
            '.xml': 'xml', '.toml': 'toml', '.ini': 'ini'
        }
        return language_map.get(ext, 'text')

    def parse_diff_with_line_numbers(self, old_content: str, new_content: str, file_path: str) -> List[DiffLine]:
        """
        Parses a diff between two strings and returns a list of DiffLine objects with line numbers.
        """
        diff_lines = list(difflib.unified_diff(
            old_content.splitlines(keepends=False),
            new_content.splitlines(keepends=False),
            fromfile=file_path + " (old)",
            tofile=file_path + " (new)",
            lineterm=''
        ))

        parsed_lines: List[DiffLine] = []
        old_line_num = 0
        new_line_num = 0

        for line in diff_lines:
            if line.startswith('---') or line.startswith('+++'):
                parsed_lines.append(DiffLine(type='hunk', content=line))
                continue

            if line.startswith('@@'):
                # Parse hunk header to reset line numbers
                # Format: @@ -old_start,old_len +new_start,new_len @@
                try:
                    parts = line.split(' ')
                    old_hunk_info = parts[1] # -old_start,old_len
                    new_hunk_info = parts[2] # +new_start,new_len
                    
                    old_line_num = int(old_hunk_info.split(',')[0].replace('-', '')) - 1
                    new_line_num = int(new_hunk_info.split(',')[0].replace('+', '')) - 1
                except ValueError:
                    # Fallback if parsing fails
                    pass
                
                parsed_lines.append(DiffLine(type='hunk', content=line))
                continue

            if line.startswith('+'):
                new_line_num += 1
                parsed_lines.append(DiffLine(type='add', content=line[1:], new_line=new_line_num))
            elif line.startswith('-'):
                old_line_num += 1
                parsed_lines.append(DiffLine(type='del', content=line[1:], old_line=old_line_num))
            else:
                old_line_num += 1
                new_line_num += 1
                parsed_lines.append(DiffLine(type='context', content=line[1:], old_line=old_line_num, new_line=new_line_num))

        return parsed_lines

    def render_diff(self, old_content: str, new_content: str, file_path: str) -> Table:
        """
        Renders the diff as a rich Table.
        """
        parsed_lines = self.parse_diff_with_line_numbers(old_content, new_content, file_path)
        language = self._infer_language(file_path)

        table = Table(show_header=False, box=None, padding=0, expand=True)
        table.add_column("Line Old", style=self.theme_colors['line_number_color'], justify="right", width=4)
        table.add_column("Line New", style=self.theme_colors['line_number_color'], justify="right", width=4)
        table.add_column("Type", width=1)
        table.add_column("Content", ratio=1)

        for line in parsed_lines:
            if line.type == 'hunk':
                table.add_row(
                    "", "", "",
                    Text(line.content, style=f"dim {self.theme_colors['diff_hunk_header_color']}")
                )
            elif line.type == 'add':
                # Crear texto con fondo verde y texto negro para mejor contraste
                content_text = Text(line.content, style="black")
                if self.use_backgrounds:
                    content_text.stylize(f"on {self.theme_colors['diff_add_color']}")
                
                table.add_row(
                    "",
                    str(line.new_line),
                    Text("+", style=f"bold {self.theme_colors['diff_add_color']}"),
                    content_text
                )
            elif line.type == 'del':
                # Crear texto con fondo rojo y texto negro para mejor contraste
                content_text = Text(line.content, style="black")
                if self.use_backgrounds:
                    content_text.stylize(f"on {self.theme_colors['diff_delete_color']}")
                
                table.add_row(
                    str(line.old_line),
                    "",
                    Text("-", style=f"bold {self.theme_colors['diff_delete_color']}"),
                    content_text
                )
            elif line.type == 'context':
                table.add_row(
                    str(line.old_line),
                    str(line.new_line),
                    " ",
                    Text(line.content, style=self.theme_colors['diff_context_color'])
                )

        return table

    def parse_diff_string(self, diff_string: str) -> List[DiffLine]:
        """
        Parses a diff string and returns a list of DiffLine objects with line numbers.
        """
        parsed_lines: List[DiffLine] = []
        old_line_num = 0
        new_line_num = 0

        for line in diff_string.splitlines():
            if line.startswith('---') or line.startswith('+++'):
                parsed_lines.append(DiffLine(type='hunk', content=line))
                continue

            if line.startswith('@@'):
                # Parse hunk header to reset line numbers
                # Format: @@ -old_start,old_len +new_start,new_len @@
                try:
                    parts = line.split(' ')
                    old_hunk_info = parts[1] # -old_start,old_len
                    new_hunk_info = parts[2] # +new_start,new_len
                    
                    old_line_num = int(old_hunk_info.split(',')[0].replace('-', '')) - 1
                    new_line_num = int(new_hunk_info.split(',')[0].replace('+', '')) - 1
                except (ValueError, IndexError):
                    # Fallback if parsing fails
                    pass
                
                parsed_lines.append(DiffLine(type='hunk', content=line))
                continue

            if line.startswith('+') and not line.startswith('+++'):
                new_line_num += 1
                parsed_lines.append(DiffLine(type='add', content=line[1:], new_line=new_line_num))
            elif line.startswith('-') and not line.startswith('---'):
                old_line_num += 1
                parsed_lines.append(DiffLine(type='del', content=line[1:], old_line=old_line_num))
            else:
                old_line_num += 1
                new_line_num += 1
                parsed_lines.append(DiffLine(type='context', content=line[1:] if line else '', old_line=old_line_num, new_line=new_line_num))

        return parsed_lines

    def render_diff_from_string(self, diff_string: str, file_path: str) -> Table:
        """
        Renders a diff string as a rich Table.
        """
        parsed_lines = self.parse_diff_string(diff_string)
        language = self._infer_language(file_path)

        table = Table(show_header=False, box=None, padding=0, expand=True)
        table.add_column("Line Old", style=self.theme_colors['line_number_color'], justify="right", width=4)
        table.add_column("Line New", style=self.theme_colors['line_number_color'], justify="right", width=4)
        table.add_column("Type", width=1)
        table.add_column("Content", ratio=1)

        for line in parsed_lines:
            if line.type == 'hunk':
                table.add_row(
                    "", "", "",
                    Text(line.content, style=f"dim {self.theme_colors['diff_hunk_header_color']}")
                )
            elif line.type == 'add':
                # Crear texto con fondo verde y texto negro para mejor contraste
                content_text = Text(line.content, style="black")
                if self.use_backgrounds:
                    content_text.stylize(f"on {self.theme_colors['diff_add_color']}")
                
                table.add_row(
                    "",
                    str(line.new_line),
                    Text("+", style=f"bold {self.theme_colors['diff_add_color']}"),
                    content_text
                )
            elif line.type == 'del':
                # Crear texto con fondo rojo y texto negro para mejor contraste
                content_text = Text(line.content, style="black")
                if self.use_backgrounds:
                    content_text.stylize(f"on {self.theme_colors['diff_delete_color']}")
                
                table.add_row(
                    str(line.old_line),
                    "",
                    Text("-", style=f"bold {self.theme_colors['diff_delete_color']}"),
                    content_text
                )
            elif line.type == 'context':
                table.add_row(
                    str(line.old_line),
                    str(line.new_line),
                    " ",
                    Text(line.content, style=self.theme_colors['diff_context_color'])
                )

        return table
