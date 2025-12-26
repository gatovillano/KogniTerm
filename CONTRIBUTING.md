# Guía de Contribución a KogniTerm

¡Gracias por tu interés en contribuir a KogniTerm! Este proyecto es posible gracias a colaboradores como tú.

Esta guía te ayudará a entender cómo puedes participar, desde reportar errores hasta proponer nuevas funcionalidades y enviar código.

## 🚀 Primeros Pasos

1. **Haz un Fork del repositorio**: Crea tu propia copia del proyecto en GitHub.
2. **Clona tu Fork**:

    ```bash
    git clone https://github.com/TU_USUARIO/kogniterm.git
    cd kogniterm
    ```

3. **Configura el entorno de desarrollo**:
    Recomendamos usar un entorno virtual:

    ```bash
    python -m venv venv
    source venv/bin/activate  # En Windows: venv\Scripts\activate
    pip install -e .
    pip install -r requirements-dev.txt # Si existe, o instala las dependencias de desarrollo necesarias
    ```

## 🛠 Flujo de Desarrollo

### Ramas (Branches)

* **`main`**: La rama principal. Debe estar siempre estable y lista para producción.
* **Feature Branches**: Crea una rama para cada nueva funcionalidad o corrección de error.
  * Formato: `feature/nombre-descriptivo` o `fix/descripcion-del-error`.
  * Ejemplo: `feature/soporte-nuevo-modelo` o `fix/error-parseo-json`.

### Estilo de Código

KogniTerm sigue estándares estrictos para mantener la calidad y legibilidad:

* **Python**: Seguimos **PEP 8**.
* **Type Hinting**: Es **obligatorio** usar type hints en todas las funciones y métodos nuevos.

    ```python
    def procesar_datos(entrada: str, opciones: Dict[str, Any]) -> Result:
        ...
    ```

* **Documentación**: Usa docstrings (formato Google o NumPy) para explicar clases y funciones complejas.
* **Formato**: Recomendamos usar `black` para formatear el código y `isort` para ordenar las importaciones.

### Pruebas (Testing)

* Asegúrate de que tu código pase todas las pruebas existentes.
* **Añade nuevas pruebas** para cualquier funcionalidad nueva o corrección de bugs.
* Ejecuta los tests con `pytest`:

    ```bash
    pytest tests/
    ```

## 📬 Enviando Cambios (Pull Requests)

1. Asegúrate de que tu código está actualizado con la rama `main` del repositorio original.
2. Ejecuta los tests localmente para confirmar que todo funciona.
3. Haz Push de tu rama a tu Fork.
4. Abre un **Pull Request (PR)** en el repositorio original.
5. Completa la plantilla del PR describiendo claramente tus cambios.

### Revisión de Código

* Un mantenedor revisará tu PR.
* Mantén una comunicación abierta y responde a los comentarios.
* Una vez aprobado, tu código será fusionado.

## 🐛 Reportando Errores (Issues)

Si encuentras un error, por favor abre un Issue en GitHub incluyendo:

* Descripción clara del problema.
* Pasos para reproducirlo.
* Comportamiento esperado vs. comportamiento real.
* Logs o capturas de pantalla si es relevante.
* Información de tu entorno (SO, versión de Python, modelo de LLM usado).

## 💡 Proponiendo Funcionalidades

Usa los Issues para proponer nuevas ideas. Describe:

* El problema que resuelve tu idea.
* La solución propuesta.
* Alternativas consideradas.

---

¡Esperamos tus contribuciones! 😺
