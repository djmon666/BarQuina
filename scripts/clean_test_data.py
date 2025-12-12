#!/usr/bin/env python3
"""
Script to reset order data from database

This script safely removes ALL orders and order items from the database
while preserving:
- Tables (Taules)
- Categories (Categories)
- Products (Productes)
- Extras definitions (Extres - configuració)
- Users (Usuaris)

Only removes transactional data (orders, payments, sessions, inventory entries).

Use this to clean test data or reset the system between events.
"""
import sys
from app import create_app, db
from app.models import (Order, OrderItem, Table, Category, Product, Payment, 
                        OrderItemExtra, PaymentItem, CashSession, InventoryEntry)

def reset_order_data(force=False):
    """
    Remove all orders and order items from database.
    
    Args:
        force (bool): Skip confirmation prompt if True
    """
    app = create_app()
    
    with app.app_context():
        print("=" * 70)
        print("🧹 RESET DE DADES DE COMANDES")
        print("=" * 70)
        print()
        
        # Count current data
        orders_count = Order.query.count()
        items_count = OrderItem.query.count()
        payments_count = Payment.query.count()
        payment_items_count = PaymentItem.query.count()
        extras_count = OrderItemExtra.query.count()
        sessions_count = CashSession.query.count()
        inventory_count = InventoryEntry.query.count()
        tables_count = Table.query.count()
        categories_count = Category.query.count()
        products_count = Product.query.count()
        
        print(f"📊 Estat actual:")
        print(f"  Comandes: {orders_count}")
        print(f"  Items de comanda: {items_count}")
        print(f"  Pagaments: {payments_count}")
        print(f"  Enllaços de pagament: {payment_items_count}")
        print(f"  Extres: {extras_count}")
        print(f"  Sessions de caixa: {sessions_count}")
        print(f"  Entrades d'inventari: {inventory_count}")
        print()
        print(f"📦 Dades que es MANTINDRAN:")
        print(f"  Taules: {tables_count}")
        print(f"  Categories: {categories_count}")
        print(f"  Productes: {products_count}")
        print(f"  Extres (configuració): es mantenen")
        print(f"  Usuaris: es mantenen")
        print()
        
        if (orders_count == 0 and items_count == 0 and payments_count == 0 
            and payment_items_count == 0 and sessions_count == 0 and inventory_count == 0):
            print("✅ La base de dades ja està neta!")
            return
        
        # Confirmation
        if not force:
            print("⚠️  ATENCIÓ: Aquesta acció esborrarà TOTES les dades de prova!")
            print("   Això inclou:")
            print("   - Totes les comandes en curs")
            print("   - L'historial de comandes")
            print("   - Tots els items de comanda")
            print("   - Tots els pagaments")
            print("   - Tots els extres")
            print("   - Totes les sessions de caixa")
            print("   - Tot l'inventari")
            print()
            print("   ES MANTINDRAN: Taules, Categories, Productes, Extres (configuració) i Usuaris")
            print()
            response = input("Vols continuar? (escriu 'SI' per confirmar): ")
            if response.upper() != 'SI':
                print("❌ Operació cancel·lada")
                sys.exit(0)
            print()
        
        print("🗑️  Esborrant dades...")
        
        try:
            # Delete in order respecting foreign keys:
            # 1. Order item extras (references order_items)
            deleted_extras = OrderItemExtra.query.delete()
            
            # 2. Payment items (links between payments and order items)
            deleted_payment_items = PaymentItem.query.delete()
            
            # 3. Inventory entries (references cash_sessions)
            deleted_inventory = InventoryEntry.query.delete()
            
            # 4. Order items (references orders)
            deleted_items = OrderItem.query.delete()
            
            # 5. Payments (references orders and cash_sessions)
            deleted_payments = Payment.query.delete()
            
            # 6. Orders (root table)
            deleted_orders = Order.query.delete()
            
            # 7. Cash sessions (root table)
            deleted_sessions = CashSession.query.delete()
            
            # Commit changes
            db.session.commit()
            
            print(f"✅ Dades esborrades correctament:")
            print(f"   - {deleted_orders} comandes")
            print(f"   - {deleted_items} items de comanda")
            print(f"   - {deleted_payments} pagaments")
            print(f"   - {deleted_payment_items} enllaços de pagament")
            print(f"   - {deleted_extras} extres")
            print(f"   - {deleted_sessions} sessions de caixa")
            print(f"   - {deleted_inventory} entrades d'inventari")
            print()
            print("📊 Estat final:")
            print(f"   Comandes: {Order.query.count()}")
            print(f"   Items: {OrderItem.query.count()}")
            print(f"   Pagaments: {Payment.query.count()}")
            print(f"   Enllaços: {PaymentItem.query.count()}")
            print(f"   Extres: {OrderItemExtra.query.count()}")
            print(f"   Sessions: {CashSession.query.count()}")
            print(f"   Inventari: {InventoryEntry.query.count()}")
            print()
            print("=" * 70)
            print("✨ Reset completat! La BD està llesta per usar.")
            print("=" * 70)
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error durant el reset: {e}")
            sys.exit(1)

if __name__ == "__main__":
    # Check for --force flag
    force = '--force' in sys.argv or '-f' in sys.argv
    
    if '--help' in sys.argv or '-h' in sys.argv:
        print("Ús: python scripts/clean_test_data.py [--force|-f]")
        print()
        print("Esborra totes les comandes i items de la base de dades.")
        print("Manté taules, categories, productes i usuaris.")
        print()
        print("Opcions:")
        print("  --force, -f    Esborra sense demanar confirmació")
        print("  --help, -h     Mostra aquest missatge")
        sys.exit(0)
    
    reset_order_data(force=force)
