#!/bin/bash
# ─── Run the schema SQL against the TimescaleDB container ────

CONTAINER_NAME="timescaledb"
DB_USER="postgres"
DB_PASS="123"
DB_NAME="micco"

echo "📋 Running schema on database '${DB_NAME}'..."

# Copy SQL file into container
docker cp init_schema.sql "${CONTAINER_NAME}":/tmp/init_schema.sql

# Execute the SQL
docker exec -e PGPASSWORD="${DB_PASS}" "${CONTAINER_NAME}" \
    psql -U "${DB_USER}" -d "${DB_NAME}" -f /tmp/init_schema.sql

echo ""
echo "════════════════════════════════════════════════"
echo "  ✅ Schema initialization complete!"
echo "════════════════════════════════════════════════"
echo ""
echo "  Tables: users, documents, chat_messages"
echo "  Functions:"
echo "    • get_dashboard_stats()"
echo "    • get_storage_by_type()"
echo "    • get_uploads_over_time()"
echo "    • search_documents(...)"
echo "    • delete_document(doc_id, user_id)"
echo "    • get_chat_history(user_id, limit)"
echo "    • insert_chat_pair(user_id, message, response, sources)"
echo ""
echo "  Seed data: 8 users, 15 documents"
echo "  Default login: alex@docvault.io"
echo "════════════════════════════════════════════════"
