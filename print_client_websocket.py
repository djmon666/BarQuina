#!/usr/bin/env python3
"""
Client d'impressió via WebSocket per Mac
Escolta events de websocket i imprimeix a la impresora tèrmica
"""

import socketio
import subprocess
import sys
from typing import Tuple

# Configuració
SERVER_URL = "http://192.168.1.220:5000"  # URL del servidor Ubuntu
PRINTER_NAME = "EPSON_TM_T20II"  # Nom de la impresora al Mac

# Crea el client Socket.IO
sio = socketio.Client()

def print_text(text: str) -> Tuple[bool, str]:
    """
    Envia text a la impresora utilitzant lpr
    """
    try:
        # Comandes ESC/POS
        ESC = b'\x1b'
        GS = b'\x1d'
        
        # Inicialitza impresora
        INIT = ESC + b'@'
        FONT_NORMAL = ESC + b'!' + b'\x00'
        FEED_LINES = b'\n' * 6
        CUT = GS + b'V\x01'  # Tall parcial
        
        # Combina tot
        full_content = INIT + FONT_NORMAL + text.encode('utf-8') + FEED_LINES + CUT
        
        # Envia amb lpr
        process = subprocess.Popen(
            ['lpr', '-P', PRINTER_NAME, '-o', 'raw'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        stdout, stderr = process.communicate(input=full_content)
        
        if process.returncode == 0:
            return True, "Imprès correctament"
        else:
            error_msg = stderr.decode('utf-8') if stderr else "Error desconegut"
            return False, f"Error: {error_msg}"
            
    except Exception as e:
        return False, f"Error: {str(e)}"

@sio.event
def connect():
    """Event de connexió"""
    print("✓ Connectat al servidor d'impressió")
    print(f"  Servidor: {SERVER_URL}")
    print(f"  Impresora: {PRINTER_NAME}")
    print("\nEsperant peticions d'impressió...")

@sio.event
def disconnect():
    """Event de desconnexió"""
    print("✗ Desconnectat del servidor")

@sio.on('print_request')
def on_print_request(data):
    """
    Event que rep peticions d'impressió
    """
    try:
        content = data.get('content', '')
        print_type = data.get('type', 'receipt')
        
        print(f"\n→ Nova petició d'impressió ({print_type})")
        
        if not content:
            print("  ✗ Error: contingut buit")
            return
        
        success, message = print_text(content)
        
        if success:
            print(f"  ✓ {message}")
        else:
            print(f"  ✗ {message}")
            
    except Exception as e:
        print(f"  ✗ Error processant impressió: {e}")

@sio.event
def connect_error(data):
    """Event d'error de connexió"""
    print(f"✗ Error de connexió: {data}")

def main():
    print("=" * 60)
    print("Client d'Impressió WebSocket per Bar Quina")
    print("=" * 60)
    print(f"Servidor: {SERVER_URL}")
    print(f"Impresora: {PRINTER_NAME}")
    print("=" * 60)
    
    try:
        # Connecta al servidor
        print("\nConnectant...")
        sio.connect(SERVER_URL)
        
        # Manté el client actiu
        sio.wait()
        
    except KeyboardInterrupt:
        print("\n\nTancant client...")
        sio.disconnect()
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
