#!/bin/bash
# Script de prueba para verificar la interrupción de comandos

echo "🧪 Iniciando prueba de interrupción..."
echo "Este script imprimirá números infinitamente."
echo "Presiona Ctrl+C o Ctrl+D para interrumpir."
echo ""

counter=1
while true; do
    echo "Contador: $counter"
    sleep 1
    counter=$((counter + 1))
done
