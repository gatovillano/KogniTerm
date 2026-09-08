import pytest
from unittest.mock import MagicMock
from kogniterm.core.utils.tool_utils import get_tool_action_description
from kogniterm.core.agents.tool_executor import ToolExecutor
from kogniterm.capabilities.registry import default_tool_registry
import kogniterm.capabilities.file_editor  # Asegura registro de capabilities
import kogniterm.capabilities.web          # Asegura registro de web capabilities


class TestToolActionDescription:
    """Verifica que la acción de las herramientas muestre la ruta del archivo o la query web."""

    def test_file_read_operations_show_path(self):
        # 1. read_file (capability o función)
        desc = get_tool_action_description("read_file", {"path": "src/main.py"})
        assert desc == "Leyendo archivo: src/main.py"

        # 2. Con rango de líneas
        desc_lines = get_tool_action_description("read_file", {"path": "src/main.py", "start_line": 10, "end_line": 50})
        assert desc_lines == "Leyendo archivo: src/main.py (líneas 10-50)"

        # 3. file_read_tool
        desc_tool = get_tool_action_description("file_read_tool", {"file_path": "/etc/hosts"})
        assert desc_tool == "Leyendo archivo: /etc/hosts"

    def test_file_edit_operations_show_path(self):
        # edit_file nativa
        desc = get_tool_action_description("edit_file", {"path": "kogniterm/app.py", "old_string": "a", "new_string": "b"})
        assert desc == "Editando archivo: kogniterm/app.py"

        # replace_all
        desc_replace = get_tool_action_description("replace_all", {"path": "config.yaml", "old_string": "x", "new_string": "y"})
        assert desc_replace == "Reemplazando en archivo: config.yaml"

        # advanced_file_editor con acción
        desc_adv = get_tool_action_description(
            "advanced_file_editor",
            {"path": "core/engine.py", "action": "insert_lines"}
        )
        assert desc_adv == "Editando archivo (insert_lines): core/engine.py"

        # file_update_tool
        desc_update = get_tool_action_description("file_update_tool", {"path": "package.json"})
        assert desc_update == "Actualizando archivo: package.json"

    def test_file_create_and_delete_operations_show_path(self):
        # create_file
        desc_create = get_tool_action_description("create_file", {"path": "new_module.py", "content": "print(1)"})
        assert desc_create == "Creando archivo: new_module.py"

        # write_file
        desc_write = get_tool_action_description("write_file", {"path": "output.txt", "content": "data"})
        assert desc_write == "Escribiendo en archivo: output.txt"

        # delete_file
        desc_delete = get_tool_action_description("delete_file", {"path": "temp.txt"})
        assert desc_delete == "Eliminando archivo: temp.txt"

    def test_directory_operations_show_path(self):
        # list_directory nativa
        desc_dir = get_tool_action_description("list_directory", {"path": "kogniterm/core"})
        assert desc_dir == "Listando directorio: kogniterm/core"

        # file_list_tool
        desc_list = get_tool_action_description("file_list_tool", {"directory": "tests/"})
        assert desc_list == "Listando directorio: tests/"

    def test_web_search_operations_show_query(self):
        # web_search nativa
        desc_search = get_tool_action_description("web_search", {"query": "python asyncio gather tutorial"})
        assert desc_search == "Buscando en la web: 'python asyncio gather tutorial'"

        # tavily_search
        desc_tavily = get_tool_action_description("tavily_search", {"query": "deepseek v3 architecture"})
        assert desc_tavily == "Buscando en la web: 'deepseek v3 architecture'"

        # duckduckgo_search
        desc_ddg = get_tool_action_description("duckduckgo_search", {"query": "rich console python"})
        assert desc_ddg == "Buscando en la web: 'rich console python'"

    def test_web_fetch_operations_show_url(self):
        # web_fetch nativa
        desc_fetch = get_tool_action_description("web_fetch", {"url": "https://api.github.com/repos/gato/kogniterm"})
        assert desc_fetch == "Consultando web: https://api.github.com/repos/gato/kogniterm"

        # browser navigation
        desc_browser = get_tool_action_description("browser_navigation", {"url": "https://news.ycombinator.com"})
        assert desc_browser == "Navegando a: https://news.ycombinator.com"

    def test_terminal_command_shows_command(self):
        desc_cmd = get_tool_action_description("execute_command", {"command": "git status --short"})
        assert desc_cmd == "Ejecutando comando: git status --short"

    def test_tool_executor_passes_dynamic_description_to_ui(self):
        """Verifica que ToolExecutor notifica a terminal_ui con la ruta o query y NO con la descripción estática."""
        mock_ui = MagicMock()
        mock_ui.is_tui = True
        mock_llm_service = MagicMock()

        # 1. Probar con capability read_file
        tc_read = {
            "name": "read_file",
            "args": {"path": "README.md"},
            "id": "call_read_1",
        }
        ToolExecutor.execute_single_tool(
            tc=tc_read,
            llm_service=mock_llm_service,
            terminal_ui=mock_ui,
        )

        # Verificar que terminal_ui.print_tool_notification fue llamado con 'Leyendo archivo: README.md'
        # y NO con la descripción estática 'Lee y retorna el contenido de un archivo...'
        assert mock_ui.print_tool_notification.called
        call_args = mock_ui.print_tool_notification.call_args
        assert call_args[0][0] == "read_file"
        action_arg = call_args[0][1]
        assert action_arg == "Leyendo archivo: README.md"
        assert "Lee y retorna el contenido" not in action_arg

        # 2. Probar con capability web_search
        mock_ui.reset_mock()
        tc_web = {
            "name": "web_search",
            "args": {"query": "langchain core messages"},
            "id": "call_web_1",
        }
        ToolExecutor.execute_single_tool(
            tc=tc_web,
            llm_service=mock_llm_service,
            terminal_ui=mock_ui,
        )

        assert mock_ui.print_tool_notification.called
        call_args_web = mock_ui.print_tool_notification.call_args
        assert call_args_web[0][0] == "web_search"
        action_arg_web = call_args_web[0][1]
        assert action_arg_web == "Buscando en la web: 'langchain core messages'"
        assert "Realiza una búsqueda rápida" not in action_arg_web
