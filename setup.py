import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Leer las dependencias de requirements.txt
with open("kogniterm/requirements.txt", "r", encoding="utf-8") as f:
    install_requires = f.read().splitlines()

setuptools.setup(
    name="kogniterm",
    version="0.1.0", # Puedes ajustar la versión según tu ciclo de desarrollo
    author="Tu Nombre/Organización", # Reemplaza con tu nombre o el de tu organización
    author_email="tu.email@example.com", # Reemplaza con tu email
    description="Un intérprete de línea de comandos interactivo que permite a los modelos de lenguaje (LLMs) ejecutar comandos en tu sistema.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/tu_usuario/kogniterm", # Reemplaza con la URL de tu repositorio GitHub
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License", # O la licencia que uses
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.9', # Asegúrate de que sea compatible con tu versión mínima de Python
    install_requires=install_requires,
    entry_points={
        'console_scripts': [
            'kogniterm=kogniterm.main:run_kogniterm',
        ],
    },
    include_package_data=True, # Para incluir archivos no Python (como requirements.txt)
    package_data={
        'kogniterm': ['requirements.txt'], # Incluir requirements.txt dentro del paquete
    },
)