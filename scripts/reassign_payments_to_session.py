#!/usr/bin/env python3
"""
Script per reassignar pagaments a sessions de caixa
basant-se en la data/hora de creació del pagament
"""

import sys
from pathlib import Path

# Afegeix el directori arrel al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from app.models import CashSession, Payment
from app.extensions import db


def reassign_payments_to_session(session_id: int, dry_run: bool = True):
    """
    Reassigna pagaments a una sessió basant-se en les dates
    
    Args:
        session_id: ID de la sessió a la qual reassignar
        dry_run: Si és True, només mostra què faria sense aplicar canvis
    """
    app = create_app()
    with app.app_context():
        session = CashSession.query.get(session_id)
        if not session:
            print(f"❌ No s'ha trobat la sessió #{session_id}")
            return
        
        print(f"📊 Sessió #{session.id}")
        print(f"   Oberta: {session.opened_at}")
        print(f"   Tancada: {session.closed_at or 'Encara oberta'}")
        print(f"   Vendes actuals: {session.total_sales:.2f}€")
        print()
        
        # Troba pagaments que haurien d'estar a aquesta sessió
        query = Payment.query.filter(
            Payment.created_at >= session.opened_at
        )
        
        # Si la sessió està tancada, només fins a la data de tancament
        if session.closed_at:
            query = query.filter(Payment.created_at <= session.closed_at)
        
        # Troba pagaments sense sessió o amb sessió incorrecta
        all_payments_in_range = query.all()
        
        payments_to_reassign = [
            p for p in all_payments_in_range 
            if p.cash_session_id != session.id
        ]
        
        if not payments_to_reassign:
            print("✅ Tots els pagaments ja estan assignats correctament")
            return
        
        print(f"🔍 Trobats {len(payments_to_reassign)} pagaments a reassignar:")
        print()
        
        total_amount = 0
        for p in payments_to_reassign:
            prev_session = f"sessió #{p.cash_session_id}" if p.cash_session_id else "sense sessió"
            print(f"   Payment #{p.id}: {p.amount:.2f}€ - {p.created_at} ({prev_session})")
            total_amount += p.amount
        
        print()
        print(f"💰 Total a reassignar: {total_amount:.2f}€")
        print(f"📈 Noves vendes totals: {session.total_sales + total_amount:.2f}€")
        print()
        
        if dry_run:
            print("🔸 MODE SIMULACIÓ - No s'han aplicat canvis")
            print("   Executa amb --apply per aplicar els canvis")
        else:
            # Aplica els canvis
            for p in payments_to_reassign:
                p.cash_session_id = session.id
            
            db.session.commit()
            print("✅ Pagaments reassignats correctament!")
            
            # Recarrega la sessió per veure els nous totals
            db.session.refresh(session)
            print(f"📊 Vendes finals: {session.total_sales:.2f}€")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Reassigna pagaments a una sessió de caixa"
    )
    parser.add_argument(
        "session_id",
        type=int,
        help="ID de la sessió a la qual reassignar pagaments"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica els canvis (per defecte només simula)"
    )
    
    args = parser.parse_args()
    
    dry_run = not args.apply
    reassign_payments_to_session(args.session_id, dry_run=dry_run)


if __name__ == "__main__":
    main()
