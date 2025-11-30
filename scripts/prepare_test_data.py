#!/usr/bin/env python3
"""
Prepare test data for load testing.

This script ensures the database has sufficient data for realistic load testing:
- Tables
- Products in different categories
- Categories (some auto-prepared, some not)

Usage:
    python scripts/prepare_test_data.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from app.extensions import db
from app.models import Table, Category, Product


def prepare_test_data():
    """Prepare database with test data."""
    app = create_app()
    
    with app.app_context():
        print("🔧 Preparing test data for load testing...")
        print()
        
        # Create tables if they don't exist
        print("📊 Creating tables...")
        existing_tables = {t.name for t in Table.query.all()}
        new_tables = 0
        
        for i in range(1, 21):  # 20 tables
            table_name = f"T{i}"
            if table_name not in existing_tables:
                table = Table(name=table_name, seats=4)
                db.session.add(table)
                new_tables += 1
        
        if new_tables > 0:
            db.session.commit()
            print(f"  ✓ Created {new_tables} new tables")
        else:
            print(f"  ✓ All tables already exist")
        
        # Create categories
        print("\n📁 Creating categories...")
        categories_config = [
            ("Begudes", True, 10),   # Auto-prepared
            ("Entrants", False, 20),
            ("Plats", False, 30),
            ("Postres", True, 40),   # Auto-prepared
            ("Cafès", True, 50),     # Auto-prepared
        ]
        
        existing_cats = {c.name for c in Category.query.all()}
        new_cats = 0
        
        for name, auto_prep, sort_order in categories_config:
            if name not in existing_cats:
                cat = Category(name=name, auto_prepare=auto_prep, sort_order=sort_order)
                db.session.add(cat)
                new_cats += 1
        
        if new_cats > 0:
            db.session.commit()
            print(f"  ✓ Created {new_cats} new categories")
        else:
            print(f"  ✓ All categories already exist")
        
        # Create products
        print("\n🍽️  Creating products...")
        products_config = [
            # Begudes (auto-prepared)
            ("Aigua", "Begudes", 1.5),
            ("Coca-Cola", "Begudes", 2.5),
            ("Cervesa", "Begudes", 2.8),
            ("Vi negre", "Begudes", 3.5),
            ("Vi blanc", "Begudes", 3.5),
            ("Cava", "Begudes", 4.5),
            # Entrants
            ("Olives", "Entrants", 3.0),
            ("Pa amb tomàquet", "Entrants", 3.5),
            ("Croquetes", "Entrants", 6.5),
            ("Patates braves", "Entrants", 5.5),
            # Plats
            ("Arròs negre", "Plats", 14.5),
            ("Fideuà", "Plats", 13.5),
            ("Entrecot", "Plats", 16.5),
            ("Bacallà", "Plats", 15.0),
            ("Pollastre", "Plats", 12.0),
            # Postres (auto-prepared)
            ("Crema catalana", "Postres", 4.5),
            ("Gelat", "Postres", 3.5),
            ("Fruita", "Postres", 3.0),
            # Cafès (auto-prepared)
            ("Cafè sol", "Cafès", 1.5),
            ("Cafè amb llet", "Cafès", 1.8),
            ("Tallat", "Cafès", 1.6),
        ]
        
        existing_products = {p.name for p in Product.query.all()}
        new_products = 0
        
        # Need to flush categories first to avoid autoflush issues
        db.session.flush()
        
        # Get all categories for product creation
        categories_map = {c.name: c for c in Category.query.all()}
        
        for name, cat_name, price in products_config:
            if name not in existing_products:
                category = categories_map.get(cat_name)
                if category:
                    product = Product(
                        name=name,
                        price=price,
                        category=category,  # Use relationship, not category_id
                        is_active=True
                    )
                    db.session.add(product)
                    new_products += 1
        
        if new_products > 0:
            db.session.commit()
            print(f"  ✓ Created {new_products} new products")
        else:
            print(f"  ✓ All products already exist")
        
        # Summary
        print("\n" + "="*60)
        print("✅ Test data preparation complete!")
        print("="*60)
        
        total_tables = Table.query.count()
        total_categories = Category.query.count()
        total_products = Product.query.count()
        
        print(f"\nDatabase now contains:")
        print(f"  📊 Tables: {total_tables}")
        print(f"  📁 Categories: {total_categories}")
        print(f"  🍽️  Products: {total_products}")
        print()


if __name__ == "__main__":
    prepare_test_data()
