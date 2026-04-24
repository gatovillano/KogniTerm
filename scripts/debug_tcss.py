import sys
from textual.css.stylesheet import Stylesheet
from textual._callback import invoke

# InlineApprovalWidget.DEFAULT_CSS content
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

    /* Título / Petición */
    #ia-title-label {
        width: 100%;
        text-style: bold;
        padding-bottom: 1;
    }

    /* Diff area */
    #ia-diff-scroll {
        width: 100%;
        height: auto;
        max-height: 20;
        margin-bottom: 1;
        border: solid #333333;
    }
    #ia-diff-container {
        width: 100%;
        height: auto;
        padding: 0;
        background: transparent;
    }
    #ia-bash-syntax {
        padding: 1 2;
    }

    /* Mensaje sin diff */
    #ia-message {
        width: 100%;
        height: auto;
        padding: 0 0 1 0;
        background: transparent;
    }

    /* Footer con botones */
    #ia-footer {
        width: 100%;
        height: auto;
        min-height: 3;
        background: transparent;
        layout: horizontal;
    }
    #ia-btn-accept, #ia-btn-accept-all, #ia-btn-cancel {
        color: #ffffff;
        border: none;
        margin-right: 1;
        width: 16;
        height: 3;
    }

    /* Versión decidida (persistente) */
    InlineApprovalWidget.decided {
        margin: 0 0 1 0;
        padding: 0 2;
        border: none;
        background: #232323;
    }
    InlineApprovalWidget.decided #ia-title-label {
        padding-bottom: 0;
        text-style: italic;
    }
    InlineApprovalWidget.decided #ia-diff-scroll {
        max-height: 12;
        border: none;
        margin-bottom: 0;
    }
    #ia-status-label {
        width: 100%;
        height: 1;
        margin-top: 0;
        text-style: bold;
    }
"""

try:
    stylesheet = Stylesheet()
    stylesheet.add_source(DEFAULT_CSS)
    # Trigger parse
    _ = stylesheet.rules
    print("CSS is valid!")
except Exception as e:
    print(f"Error caught: {e.__class__.__name__}: {e}")
    if hasattr(e, 'errors'):
        print("Detailed errors:")
        for error in e.errors:
            print(f" - {error}")
    elif hasattr(e, 'renderable'):
         # It seems StylesheetParseError has a 'renderable' attribute which is StylesheetErrors
         from rich.console import Console
         console = Console()
         console.print(e.renderable)
