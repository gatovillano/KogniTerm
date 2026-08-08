from rich.markdown import Markdown
from kogniterm.ui.terminal_ui import TerminalUI

def test_print_confirmation_panel_rendering():
    """Verifica que print_confirmation_panel no genere AttributeError por box=None."""
    ui = TerminalUI()
    content = Markdown("¿Desea ejecutar `echo hello`?")
    title = "Aprobación de Comando"
    
    # Debe ejecutarse sin lanzar excepciones (como AttributeError: 'NoneType' object has no attribute 'substitute')
    ui.print_confirmation_panel(content, title, "yellow")
