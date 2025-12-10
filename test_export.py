#!/usr/bin/env python3
"""Test script to verify export functionality."""

import sys
from app import create_app, db
from app.models import CashSession

def test_exports():
    """Test PDF and Excel export functions."""
    app = create_app()
    
    with app.app_context():
        # Get the first session
        session = CashSession.query.first()
        
        if not session:
            print("❌ No hi ha cap sessió a la base de dades")
            return False
        
        print(f"✓ Sessió trobada: #{session.id}")
        
        # Test PDF export
        try:
            from app.blueprints.reports.routes import _get_session_data
            data = _get_session_data(session.id)
            
            if data:
                print(f"✓ Dades de sessió obtingudes:")
                print(f"  - Productes venuts: {len(data['products_sold'])}")
                print(f"  - Ingressos: {data['revenue']:.2f} €")
                print(f"  - Costos: {data['costs']:.2f} €")
                print(f"  - Benefici: {data['profit']:.2f} €")
                print(f"  - Entrades inventari: {len(data['inventory_entries'])}")
            else:
                print("❌ No s'han pogut obtenir les dades")
                return False
        
        except Exception as e:
            print(f"❌ Error al processar dades: {e}")
            return False
        
        print("\n✓ Tot correcte! Les exportacions haurien de funcionar.")
        print("Per provar-ho:")
        print(f"  - PDF: http://localhost:5000/reports/export/pdf/{session.id}")
        print(f"  - Excel: http://localhost:5000/reports/export/excel/{session.id}")
        
        return True

if __name__ == "__main__":
    success = test_exports()
    sys.exit(0 if success else 1)
