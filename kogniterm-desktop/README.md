# KogniTerm Desktop

Una aplicación de escritorio moderna para KogniTerm construida con Tauri, React y FastAPI.

## 🚀 Características

- **Chat Inteligente**: Interfaz de chat con streaming en tiempo real
- **Terminal Integrada**: Terminal XTerm.js completamente funcional
- **Explorador de Archivos**: Navegación de archivos del proyecto
- **Arquitectura Híbrida**: Frontend en Tauri/React + Backend en Python/FastAPI
- **Diseño Premium**: UI moderna con Tailwind CSS y tema oscuro

## 📋 Requisitos Previos

- **Node.js** >= 18.x
- **Python** >= 3.9
- **Rust** (para Tauri)
- **Dependencias del sistema** (Linux):
  - `webkit2gtk-4.1`
  - `librsvg2-dev`
  - `build-essential`

### Instalación de dependencias en Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install libwebkit2gtk-4.1-dev \
  build-essential \
  curl \
  wget \
  file \
  libssl-dev \
  libayatana-appindicator3-dev \
  librsvg2-dev
```

## 🛠️ Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/gatovillano/KogniTerm.git
cd KogniTerm/kogniterm-desktop
```

### 2. Instalar dependencias del monorepo

```bash
npm install
```

### 3. Instalar dependencias de Python

```bash
cd apps/server
pip install -r requirements.txt
cd ../..
```

## 🚀 Desarrollo

Para ejecutar la aplicación en modo desarrollo, necesitas **dos terminales**:

### Terminal 1: Backend (Python/FastAPI)

```bash
cd apps/server
python dev.py
```

El servidor estará disponible en `http://localhost:8000`

### Terminal 2: Frontend (Tauri/React)

```bash
cd apps/desktop
npm run tauri dev
```

Esto abrirá la aplicación desktop en modo desarrollo con hot-reload.

## 📦 Build de Producción

### Backend

```bash
cd apps/server
# Crear un ejecutable con PyInstaller (opcional)
pip install pyinstaller
pyinstaller --onefile dev.py
```

### Frontend

```bash
cd apps/desktop
npm run tauri build
```

Los binarios estarán en `apps/desktop/src-tauri/target/release/`

## 🏗️ Estructura del Proyecto

```
kogniterm-desktop/
├── apps/
│   ├── desktop/          # Aplicación Tauri + React
│   │   ├── src/          # Código fuente React
│   │   ├── src-tauri/    # Código Rust de Tauri
│   │   └── package.json
│   └── server/           # Backend FastAPI
│       ├── kogniterm_server/
│       │   ├── api/      # Endpoints REST
│       │   └── core/     # Adaptador de KogniTerm
│       └── requirements.txt
├── package.json          # Configuración del monorepo
└── turbo.json           # Configuración de Turbo
```

## 🔧 Configuración

### Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto:

```env
# API Keys
OPENROUTER_API_KEY=tu_api_key
LITELLM_MODEL=openrouter/google/gemini-2.0-flash-exp:free

# O usa Google AI Studio
GOOGLE_API_KEY=tu_api_key
GEMINI_MODEL=gemini-2.0-flash-exp
```

## 📚 Tecnologías Utilizadas

### Frontend

- **Tauri** - Framework de aplicaciones desktop
- **React** - Biblioteca UI
- **TypeScript** - Tipado estático
- **Tailwind CSS** - Framework de estilos
- **XTerm.js** - Emulador de terminal
- **React Markdown** - Renderizado de Markdown
- **Lucide React** - Iconos

### Backend

- **FastAPI** - Framework web asíncrono
- **Uvicorn** - Servidor ASGI
- **WebSockets** - Comunicación en tiempo real
- **KogniTerm Core** - Lógica de agentes

### Build Tools

- **Turbo** - Monorepo build system
- **Vite** - Build tool para React
- **Cargo** - Build tool para Rust

## 🤝 Contribuir

Las contribuciones son bienvenidas. Por favor:

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📝 Licencia

Este proyecto está bajo la licencia MIT. Ver `LICENSE` para más información.

## 🐛 Reportar Bugs

Si encuentras un bug, por favor abre un issue en [GitHub Issues](https://github.com/gatovillano/KogniTerm/issues).

## 📧 Contacto

Gato Villano - [@gatovillano](https://github.com/gatovillano)

Proyecto: [https://github.com/gatovillano/KogniTerm](https://github.com/gatovillano/KogniTerm)
