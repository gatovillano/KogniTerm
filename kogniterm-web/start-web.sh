#!/usr/bin/env bash
# Script de inicio rápido para Kogniterm Web

echo "=================================================="
echo "  Iniciando Kogniterm Web (Frontend Ultra-Premium)"
echo "=================================================="

cd "$(dirname "$0")"

if [ ! -d "node_modules" ]; then
  echo "📦 Instalando dependencias..."
  npm install
fi

echo "🚀 Lanzando servidor de desarrollo en http://localhost:3000 ..."
echo "ℹ️  Asegúrate de que kogniterm-server esté corriendo en http://localhost:8765"
echo ""

npm run dev
