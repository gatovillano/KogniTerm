from kogniterm.terminal.tui.components.tool_output import ToolOutputWidget
w = ToolOutputWidget("Hello\nWorld", "term")
w._render_pyte("Line 1\nLine 2")
print("Rendered successfully")
