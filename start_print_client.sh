#!/bin/bash
# Script per iniciar el client d'impressió WebSocket al Mac

echo "====================================================="
echo "Iniciant Client d'Impressió WebSocket"
echo "====================================================="

# Comprova si està instal·lat python-socketio
if ! python3 -c "import socketio" 2>/dev/null; then
    echo "Instal·lant dependències..."
    pip3 install python-socketio[client]
fi

# Executa el client
echo ""
python3 print_client_websocket.py
