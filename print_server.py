#!/usr/bin/env python3
"""
Servidor d'impressió per Epson TM-T20
Escolta peticions per imprimir tiquets a la impresora tèrmica
"""

import subprocess
import sys
from typing import Tuple
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Permet peticions des de qualsevol origen

# Nom de la impresora (canvia segons la configuració del Mac)
PRINTER_NAME = "EPSON_TM_T20II"  # Modifica amb el nom exacte de la impresora

def format_thermal_receipt(content: str, width: int = 48) -> str:
    """
    Formata el contingut per a impressió tèrmica
    Ample de 48 caràcters per paper de 80mm
    """
    lines = []
    for line in content.split('\n'):
        if line.strip():
            lines.append(line)
        else:
            lines.append('')
    return '\n'.join(lines)

def print_text(text: str) -> Tuple[bool, str]:
    """
    Envia text a la impresora utilitzant lpr amb opcions RAW
    per evitar formatatge de CUPS
    """
    try:
        # Comandes ESC/POS
        ESC = b'\x1b'
        GS = b'\x1d'
        
        # Inicialitza impresora en mode text
        INIT = ESC + b'@'
        
        # Configura mida de lletra normal (12x24)
        FONT_NORMAL = ESC + b'!' + b'\x00'
        
        # Afegeix línies buides i comanda de tall
        FEED_LINES = b'\n' * 6
        CUT = GS + b'V\x01'  # Tall parcial
        
        # Combina tot
        full_content = INIT + FONT_NORMAL + text.encode('utf-8') + FEED_LINES + CUT
        
        # Envia amb lpr en mode RAW (sense processar)
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
            return False, f"Error d'impressió: {error_msg}"
            
    except FileNotFoundError:
        return False, "Comanda lpr no trobada. Assegura't que CUPS està instal·lat"
    except Exception as e:
        return False, f"Error: {str(e)}"

@app.route('/health', methods=['GET'])
def health():
    """Endpoint per comprovar que el servidor està actiu"""
    return jsonify({
        'status': 'ok',
        'printer': PRINTER_NAME,
        'message': 'Servidor d\'impressió actiu'
    })

@app.route('/print', methods=['POST'])
def print_receipt():
    """
    Endpoint per imprimir un tiquet
    Espera JSON amb: { "content": "text a imprimir" }
    """
    try:
        data = request.get_json()
        
        if not data or 'content' not in data:
            return jsonify({
                'success': False,
                'error': 'Cal proporcionar "content" al JSON'
            }), 400
        
        content = data['content']
        
        # Formata i imprimeix
        formatted_content = format_thermal_receipt(content)
        success, message = print_text(formatted_content)
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/test', methods=['GET'])
def test_print():
    """Endpoint per provar la impresora"""
    test_content = """
================================================
                  BAR QUINA
================================================

              TEST D'IMPRESSIÓ

Aquest és un tiquet de prova per verificar
que la impresora funciona correctament.

Data: Test
Hora: Test

================================================
              Gràcies per la seva visita!
================================================


"""
    success, message = print_text(test_content)
    
    if success:
        return jsonify({
            'success': True,
            'message': 'Tiquet de prova imprès correctament'
        })
    else:
        return jsonify({
            'success': False,
            'error': message
        }), 500

if __name__ == '__main__':
    print("=" * 50)
    print("Servidor d'impressió per Bar Quina")
    print("=" * 50)
    print(f"Impresora configurada: {PRINTER_NAME}")
    print("Escoltant a: http://192.168.1.36:5000")
    print("\nEndpoints disponibles:")
    print("  GET  /health - Comprovar estat")
    print("  GET  /test   - Imprimir tiquet de prova")
    print("  POST /print  - Imprimir tiquet (JSON amb 'content')")
    print("=" * 50)
    
    # Executa el servidor
    app.run(host='0.0.0.0', port=5000, debug=False)
