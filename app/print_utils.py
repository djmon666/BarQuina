"""
Utilitats per generar i enviar tiquets a la impresora tèrmica
"""

from datetime import datetime
import requests
from typing import Optional, Tuple
from .models import Order, Payment

# Configuració del servidor d'impressió
PRINT_SERVER_URL = "http://192.168.1.36:5000/print"
PRINT_ENABLED = True  # Canvia a False per deshabilitar impressió

def center_text(text: str, width: int = 48) -> str:
    """Centra text dins l'ample del paper"""
    return text.center(width)

def line_separator(char: str = "=", width: int = 48) -> str:
    """Genera una línia separadora"""
    return char * width

def format_price(amount: float) -> str:
    """Formata un preu amb 2 decimals"""
    return f"EUR {amount:.2f}"

def normalize_text(text: str) -> str:
    """Elimina accents i caràcters especials per compatibilitat amb impresores tèrmiques"""
    replacements = {
        'à': 'a', 'á': 'a', 'è': 'e', 'é': 'e', 'í': 'i', 'ï': 'i',
        'ò': 'o', 'ó': 'o', 'ú': 'u', 'ü': 'u', 'ç': 'c',
        'À': 'A', 'Á': 'A', 'È': 'E', 'É': 'E', 'Í': 'I', 'Ï': 'I',
        'Ò': 'O', 'Ó': 'O', 'Ú': 'U', 'Ü': 'U', 'Ç': 'C',
        '/': '-'
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text

def left_right_text(left: str, right: str, width: int = 48) -> str:
    """Alinea text a l'esquerra i dreta"""
    spaces = width - len(left) - len(right)
    if spaces < 1:
        spaces = 1
    return f"{left}{' ' * spaces}{right}"

def generate_payment_receipt(order: Order, payment: Payment, cash_given: float = 0.0) -> str:
    """
    Genera el contingut del tiquet de caixa
    
    Args:
        order: Comanda cobrada
        payment: Pagament registrat
        cash_given: Efectiu donat pel client (per calcular canvi)
    """
    lines = []
    width = 48
    
    # Capçalera
    lines.append("")
    lines.append(line_separator())
    lines.append(center_text("BAR QUINA"))
    lines.append(line_separator())
    lines.append("")
    
    # Informació de la comanda
    lines.append(center_text(f"COMANDA #{order.id}", width))
    lines.append(center_text(f"Taula: {normalize_text(order.table.name)}", width))
    if order.created_by:
        lines.append(center_text(f"Cambrer/a: {normalize_text(order.created_by.name)}", width))
    lines.append("")
    lines.append(center_text(datetime.now().strftime("%d/%m/%Y %H:%M"), width))
    lines.append("")
    lines.append(line_separator("-"))
    lines.append("")
    
    # Productes
    for item in order.items:
        # Nom del producte i quantitat
        product_line = f"{item.quantity}x {normalize_text(item.product.name)}"
        lines.append(product_line)
        # Preu en línia separada alineat a la dreta
        price = format_price(item.quantity * item.unit_price)
        lines.append(" " * (width - len(price)) + price)
        
        # Extres
        if item.extras:
            for extra in item.extras:
                extra_line = f"   + {normalize_text(extra.label)} (x{extra.quantity})"
                lines.append(extra_line)
                extra_price = format_price(extra.total())
                lines.append(" " * (width - len(extra_price)) + extra_price)
    
    lines.append("")
    lines.append(line_separator("-"))
    lines.append("")
    
    # Totals
    lines.append(left_right_text("SUBTOTAL:", format_price(order.subtotal()), width))
    lines.append("")
    lines.append(left_right_text("TOTAL:", format_price(payment.amount), width))
    lines.append("")
    
    # Informació de pagament
    method_labels = {
        'efectiu': 'EFECTIU',
        'targeta': 'TARGETA',
        'mixt': 'MIXT'
    }
    payment_method = method_labels.get(payment.method.value, payment.method.value.upper())
    lines.append(left_right_text(f"Pagament: {payment_method}", "", width))
    
    # Mostrar efectiu donat i canvi
    
    lines.append("")
    lines.append(left_right_text("PAGAT:", format_price(cash_given), width))
    change = cash_given - payment.amount
    if change >= 0:
        lines.append(left_right_text("CANVI:", format_price(change), width))
    elif change < 0:
        # Si cash_given és menor que el total (pagament parcial)
        lines.append(left_right_text("PENDENT:", format_price(abs(change)), width))
    
    lines.append("")
    lines.append(line_separator())
    lines.append(center_text("Gracies per la seva visita!", width))
    lines.append(line_separator())
    lines.append("")
    lines.append("")
    lines.append("")
    
    return "\n".join(lines)

def generate_kitchen_receipt(order: Order) -> str:
    """
    Genera el contingut del tiquet de cuina
    Només mostra productes pendents o en preparació
    
    Args:
        order: Comanda a preparar
    """
    lines = []
    width = 48
    
    # Capçalera amb número de comanda gran
    lines.append("")
    lines.append(line_separator())
    lines.append(center_text("*** CUINA ***", width))
    lines.append(line_separator())
    lines.append("")
    lines.append(center_text(f"COMANDA #{order.id}", width))
    lines.append(center_text("=" * 20, width))
    lines.append(center_text(f"# {order.id} #", width))
    lines.append(center_text("=" * 20, width))
    lines.append("")
    
    # Informació
    lines.append(center_text(f"Taula: {normalize_text(order.table.name)}", width))
    lines.append(center_text(datetime.now().strftime("%H:%M"), width))
    lines.append("")
    lines.append(line_separator("-"))
    lines.append("")
    
    # Productes (només els que cal preparar)
    items_to_prepare = [item for item in order.items 
                       if item.status.value in ['pendent', 'preparat']]
    
    if not items_to_prepare:
        lines.append(center_text("(Tots els productes servits)", width))
    else:
        for item in items_to_prepare:
            # Quantitat i producte en gran
            lines.append(f"{item.quantity}x {normalize_text(item.product.name)}".upper())
            
            # Extres (MOLT IMPORTANT)
            if item.extras:
                lines.append("")
                lines.append("   EXTRES:")
                for extra in item.extras:
                    lines.append(f"   - {normalize_text(extra.label)} x{extra.quantity}")
                lines.append("")
            
            # Notes si n'hi ha
            if item.notes:
                lines.append(f"   Nota: {normalize_text(item.notes)}")
                lines.append("")
            
            lines.append(line_separator("-", width))
    
    lines.append("")
    lines.append(center_text(f"Total articles: {sum(i.quantity for i in items_to_prepare)}", width))
    lines.append("")
    lines.append(line_separator())
    lines.append("")
    lines.append("")
    lines.append("")
    
    return "\n".join(lines)

def send_to_printer(content: str) -> Tuple[bool, str]:
    """
    Envia el contingut a la impresora via servidor d'impressió
    
    Returns:
        (success, message): Tupla amb resultat i missatge
    """
    if not PRINT_ENABLED:
        return False, "Impressió deshabilitada"
    
    try:
        response = requests.post(
            PRINT_SERVER_URL,
            json={'content': content},
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get('success', False), data.get('message', 'Imprès')
        else:
            error_data = response.json()
            return False, error_data.get('error', 'Error desconegut')
            
    except requests.exceptions.ConnectionError:
        return False, "No es pot connectar amb el servidor d'impressió"
    except requests.exceptions.Timeout:
        return False, "Temps d'espera exhaurit"
    except Exception as e:
        return False, f"Error: {str(e)}"

def print_payment_receipt(order: Order, payment: Payment, cash_given: float = 0.0) -> Tuple[bool, str]:
    """
    Genera i imprimeix tiquet de caixa
    """
    content = generate_payment_receipt(order, payment, cash_given)
    return send_to_printer(content)

def print_kitchen_receipt(order: Order) -> Tuple[bool, str]:
    """
    Genera i imprimeix tiquet de cuina
    """
    content = generate_kitchen_receipt(order)
    return send_to_printer(content)
