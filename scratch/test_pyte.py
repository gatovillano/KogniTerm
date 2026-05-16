import pyte
screen = pyte.Screen(80, 24)
stream = pyte.Stream(screen)
stream.feed("Hello World")
print(screen.display)
