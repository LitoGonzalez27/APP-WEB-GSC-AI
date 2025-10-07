#!/bin/bash
set -e

echo "🎭 Installing Playwright Chromium..."
playwright install chromium

echo "🔧 Running database migrations..."
python3 fix_quota_events_table.py || echo "⚠️ Migration already applied or failed (non-critical)"



