#!/usr/bin/env python3
"""Create an admin user."""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from app.extensions import db
from app.models import StaffUser, UserRole


def main():
    app = create_app()
    with app.app_context():
        name = input("Nom d'usuari admin: ").strip()
        if not name:
            print("El nom d'usuari no pot estar buit")
            return

        # Check if user exists
        existing = StaffUser.query.filter_by(name=name).first()
        if existing:
            print(f"L'usuari '{name}' ja existeix")
            return

        password = getpass.getpass("Contrasenya: ")
        password_confirm = getpass.getpass("Confirma contrasenya: ")

        if password != password_confirm:
            print("Les contrasenyes no coincideixen")
            return

        if len(password) < 4:
            print("La contrasenya ha de tenir almenys 4 caràcters")
            return

        # Create admin user
        admin = StaffUser(name=name, role=UserRole.ADMIN, is_active=True)
        admin.set_password(password)

        db.session.add(admin)
        db.session.commit()

        print(f"✓ Usuari admin '{name}' creat correctament")


if __name__ == "__main__":
    main()
