#!/bin/bash
echo "🚀 Memulai Deployment Docker AuditLens AI Core (PT Suryamicrosystem)..."
if [ ! -f audit_system.db ]; then
    touch audit_system.db
fi
docker-compose down
docker-compose build --no-cache
docker-compose up -d
echo "✅ Sistem Berhasil Dijalankan di: http://localhost:8501"
