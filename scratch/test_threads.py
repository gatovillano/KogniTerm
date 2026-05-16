
import threading
from concurrent.futures import ThreadPoolExecutor

def task(name):
    print(f"Task {name} starting")
    return f"Result {name}"

def main():
    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(task, "A")
        f2 = executor.submit(task, "B")
        print(f1.result())
        print(f2.result())

if __name__ == "__main__":
    main()
