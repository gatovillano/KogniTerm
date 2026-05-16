from rich.console import Console
from rich.panel import Panel
from rich.text import Text
import pyte

console = Console(width=80, force_terminal=True, color_system="truecolor")
panel = Panel("Hello World", title="My Panel")

with console.capture() as capture:
    console.print(panel)
data = capture.get()

print("DATA LENGTH:", len(data))
print("DATA REPR:", repr(data[:50]))

screen = pyte.Screen(80, 24)
stream = pyte.Stream(screen)
stream.feed(data)

lines = []
for y in range(screen.lines):
    line = "".join(c.data for c in screen.buffer[y])
    lines.append(line)

print("SCREEN OUT:")
for line in lines:
    if line.strip():
        print(repr(line))

