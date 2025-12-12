#!/bin/bash
# Script per preparar la base de dades per producció
# 1. Fa una còpia de seguretat
# 2. Esborra les dades de prova

set -e  # Sortir si hi ha errors

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  PREPARACIÓ PER PRODUCCIÓ - BarQuina                          ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Anar al directori del projecte
cd "$(dirname "$0")/.."

# Activar entorn virtual si existeix
if [ -d ".venv" ]; then
    echo "🐍 Activant entorn virtual..."
    source .venv/bin/activate
elif [ -d "venv" ]; then
    echo "🐍 Activant entorn virtual..."
    source venv/bin/activate
fi

# 1. BACKUP
echo ""
echo "📦 PAS 1: Creant còpia de seguretat..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python scripts/backup_db.py --dest ./backups --retain 50

if [ $? -ne 0 ]; then
    echo "❌ Error creant el backup!"
    exit 1
fi

echo ""
echo "✅ Còpia de seguretat creada correctament!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 2. NETEJA
echo ""
echo "🧹 PAS 2: Esborrant dades de prova..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
PYTHONPATH=$(pwd) python scripts/clean_test_data.py

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Error esborrant les dades!"
    echo "⚠️  La còpia de seguretat està a ./backups/"
    exit 1
fi

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  ✨ SISTEMA LLEST PER PRODUCCIÓ! ✨                            ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "📋 Resum:"
echo "  ✅ Còpia de seguretat creada a ./backups/"
echo "  ✅ Dades de prova esborrades"
echo "  ✅ Productes, Categories, Taules i Usuaris conservats"
echo ""
echo "🚀 Ja pots obrir el bar i començar a treballar!"
echo ""
