# 📊 Dashboard de Estadísticas de KogniTerm

Panel web para visualizar estadísticas de uso del repositorio KogniTerm.

## � Características

- **Estadísticas en tiempo real** desde la API de GitHub
- **Gráficos de tráfico** (clonaciones y vistas)
- **Diseño responsive** con tema oscuro
- **Actualización automática** configurable
- **Sin dependencias** - HTML/CSS/JS puro

## 📋 Datos mostrados

### Métricas principales
- **Clonaciones totales**: 1,057
- **Clonaciones únicas**: 225
- **Vistas totales**: 147
- **Vistas únicas**: 28

### Información del repositorio
- ⭐ Estrellas
- 🍴 Forks
- 👥 Contribuidores
- 🏷️ Releases
- 📅 Fechas de creación y última actualización

### Tráfico detallado
- Gráfico de clonaciones por día
- Gráfico de vistas por día
- Tabla con datos históricos

## ⚙️ Configuración

### 1. Obtener un token de GitHub

1. Ve a https://github.com/settings/tokens
2. Click en "Generate new token" → "Generate new token (classic)"
3. Dale un nombre (ej: "KogniTerm Dashboard")
4. Selecciona el scope: `public_repo`
5. Click en "Generate token"
6. Copia el token generado

### 2. Configurar el dashboard

Edita el archivo `config.json`:

```json
{
  "github_token": "TU_TOKEN_AQUÍ",
  "repo_owner": "gatovillano",
  "repo_name": "KogniTerm",
  "refresh_interval": 1800000
}
```

### 3. Servir el dashboard

Opción A - Usar Python (recomendado):
```bash
cd dashboard
python3 -m http.server 8080
```

Opción B - Usar Node.js:
```bash
npx serve dashboard -p 8080
```

Opción C - Usar PHP:
```bash
php -S localhost:8080 -t dashboard
```

Luego abre: http://localhost:8080

## 🔒 Notas de seguridad

- **Nunca** compartas tu token de GitHub públicamente
- El archivo `config.json` está en `.gitignore` por defecto
- Si usas GitHub Pages, configura el token desde variables de entorno del servidor
- Para producción, considera usar un proxy backend para ocultar el token

## 📈 Interpretación de datos

### Clonaciones
- **Total**: Número de veces que se clonó el repositorio
- **Únicas**: Número de usuarios únicos que clonaron
- **Ratio**: ~4.7 clonaciones por usuario único

### Vistas
- **Total**: Veces que se visitó la página del repo
- **Únicas**: Visitantes únicos
- **Ratio**: ~5.3 vistas por visitante único

### Tendencia reciente
- Pico de actividad: 14 de junio (268 clones, 56 únicos)
- Actividad constante desde el 7 de junio
- Sin actividad los primeros días del período

## 🛠️ Personalización

### Cambiar colores
Edita las variables CSS en `index.html`:
```css
:root {
    --primary: #00d4ff;      /* Color principal */
    --secondary: #7b2cbf;    /* Color secundario */
    --accent-green: #00ff88; /* Éxito/positivo */
    --accent-yellow: #ffd700; /* Advertencia */
    --accent-red: #ff4757;   /* Error/peligro */
}
```

### Cambiar intervalo de actualización
```json
{
  "refresh_interval": 3600000  // 1 hora en milisegundos
}
```

## 📊 Datos actuales (Junio 2026)

| Métrica | Valor |
|---------|-------|
| Clonaciones totales | 1,057 |
| Clonaciones únicas | 225 |
| Vistas totales | 147 |
| Vistas únicas | 28 |
| Contribuidores | 2 |
| Releases | 2 |
| Idioma principal | Python |

## 🔄 Actualizaciones futuras

Para obtener estadísticas de instalaciones reales (no solo clones), se puede:

1. **Agregar tracking en install.sh**: Un beacon anónimo a un endpoint
2. **Usar GitHub Releases**: Contar descargas de assets
3. **Implementar un endpoint propio**: Recibir eventos de instalación

## 📄 Licencia

Este dashboard es parte del proyecto KogniTerm.
