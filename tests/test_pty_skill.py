import os
import sys
# Adicionar el directorio raíz al path para importar kogniterm
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from kogniterm.skills.bundled.execute_command.scripts.tool import execute_command

def test_pty_output():
    print("Testing PTY output with 'ls --color=always'...")
    # 'ls --color=always' produce códigos ANSI si detecta un TTY (o si se fuerza)
    # Con PTY debería funcionar siempre.
    generator = execute_command("ls --color=always", timeout=5)
    
    full_output = ""
    for chunk in generator:
        full_output += chunk
        # print(chunk, end="", flush=True)
    
    # Verificar si hay códigos de escape ANSI (indicativo de que ls detectó un TTY/PTY)
    if "\x1b[" in full_output:
        print("\n✅ Éxito: Se detectaron códigos ANSI en la salida.")
    else:
        print("\n❌ Error: No se detectaron códigos ANSI. ¿Es un PTY real?")
        
    print(f"Salida total (primeros 100 caracteres): {repr(full_output[:100])}")

def test_pty_interactivity():
    print("\nTesting PTY interactivity with 'read' command...")
    # Usar un comando que espere entrada
    generator = execute_command("read -p 'Enter something: ' var && echo \"You entered: $var\"", timeout=5)
    
    try:
        # 1. Obtener el prompt
        prompt = next(generator)
        print(f"Prompt recibido: {repr(prompt)}")
        
        # 2. Enviar respuesta
        # Enviar vía .send() al generador
        output = generator.send("Hola PTY\n")
        print(f"Respuesta después de enviar input: {repr(output)}")
        
        # 3. Seguir consumiendo
        for chunk in generator:
            print(f"Chunk extra: {repr(chunk)}")
            output += chunk
            
        if "You entered: Hola PTY" in output:
            print("✅ Éxito: Interactividad confirmada.")
        else:
            print("❌ Error: No se recibió la confirmación esperada.")
    except StopIteration:
        print("❌ Error: El generador terminó antes de tiempo.")

if __name__ == "__main__":
    test_pty_output()
    test_pty_interactivity()
