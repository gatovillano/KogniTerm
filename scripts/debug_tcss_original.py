import sys
from textual.css.stylesheet import Stylesheet
from rich.console import Console

# Original InlineApprovalWidget.DEFAULT_CSS content (with errors)
DEFAULT_CSS = """
    _DiffLineWidget {
        width: 100%;
        height: 1;
    }

    InlineApprovalWidget {
        width: 85%;
        max-width: 180;
        min-width: 60;
        height: auto;
        margin: 1 0;
        padding: 1 2;
    }

    /* Versión decidida (persistente) */
    InlineApprovalWidget.decided {
        margin: 0 0 1 0;
        padding: 0.5 2;
        border: none;
        background: #232323;
        opacity: 0.9;
    }
"""

console = Console()
try:
    stylesheet = Stylesheet()
    stylesheet.add_source(DEFAULT_CSS)
    _ = stylesheet.rules
    print("CSS is valid!")
except Exception as e:
    print(f"Error caught: {e.__class__.__name__}")
    if hasattr(e, 'errors'):
        for error in e.errors:
            console.print(error)
    elif hasattr(e, 'renderable'):
         console.print(e.renderable)
