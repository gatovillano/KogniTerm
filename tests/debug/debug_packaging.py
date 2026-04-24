from setuptools import find_packages

print("Buscando paquetes en '.' con include=['kogniterm*']...")
packages = find_packages(where=".", include=["kogniterm*"])
print("Paquetes encontrados:")
for p in packages:
    print(f" - {p}")

if "kogniterm" not in packages:
    print("\n¡ALERTA! El paquete raíz 'kogniterm' no fue encontrado.")
else:
    print("\nEl paquete raíz 'kogniterm' fue encontrado correctamente.")