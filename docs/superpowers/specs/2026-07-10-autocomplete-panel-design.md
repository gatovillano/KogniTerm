# Especificación de Diseño: Panel de Autocompletado sobre Inputbar

Este documento detalla el diseño para reemplazar el menú emergente flotante del autocompletado por un panel de ancho completo posicionado inmediatamente encima del contenedor de entrada de texto (inputbar).

## Contexto y Motivación

Actualmente, al escribir `@` (para archivos), `%` (comandos internos), `/` (comandos del sistema) o `:` (contenedores docker), aparece un menú flotante (`command_popup`) con ancho fijo de 44 caracteres alineado con la posición horizontal del cursor. 

El usuario ha solicitado que este menú contextual sea reemplazado por un panel posicionado inmediatamente sobre la barra de entrada (`inputbar`) y que tenga exactamente el mismo ancho que esta barra.

## Diseño Propuesto

### 1. Modificación de Estilos CSS (`tui_app.py`)
Eliminaremos la propiedad estática de ancho (`width: 44;`) del selector `#command_popup` en la especificación CSS para permitir que el ancho se controle dinámicamente desde el código Python en función de las dimensiones reales del contenedor del inputbar.

### 2. Ajuste Dinámico de Geometría (`_reposition_popup`)
La función `_reposition_popup` en [tui_app.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/terminal/tui/tui_app.py) se reescribirá para:
- Detectar el contenedor padre del widget de entrada activo (`input_widget.parent`), que en el chat normal es `#input_container` y en el splash screen es `#splash_input_row`.
- Leer la región física de este contenedor padre (`container_region`).
- Establecer el ancho del popup dinámicamente a la anchura de este contenedor: `self.command_popup.styles.width = container_region.width`.
- Calcular de forma precisa el alto del popup en base a la cantidad de ítems a mostrar para evitar gaps (huecos verticales): `popup_height = min(len(self.command_popup.children) + 2, 14)` (se suman 2 líneas de margen correspondientes a los bordes superior e inferior).
- Posicionar el panel de autocompletado en el eje X alineado al inicio del contenedor (`container_region.x`) y en el eje Y en `container_region.y - popup_height`.

## Plan de Verificación

### Verificación Manual
- Iniciar KogniTerm en modo interactivo (`python -m kogniterm`).
- **Pantalla de bienvenida (Splash)**: Escribir `@` o `%` en el campo del splash. Verificar que el panel de sugerencias aparezca alineado exactamente arriba de la barra de entrada del splash con el mismo ancho que ella, y que se cierre al seleccionar una opción o vaciar el texto.
- **Pantalla de chat principal**: Presionar `Enter` en el splash para entrar al chat. Escribir `@` en el campo de entrada inferior. Confirmar que el panel aparezca alineado con la caja inferior `#input_container` y tenga su mismo ancho.
- **Redimensionamiento de terminal**: Cambiar el tamaño de la terminal y verificar que el ancho del panel se adapte automáticamente al escribir o borrar texto.
- **Variabilidad de ítems**: Comprobar con 1, 5 y más de 15 ítems (con scrollbar) que no queden huecos flotantes vacíos entre el panel de autocompletado y la barra de entrada.
