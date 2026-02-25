#!/bin/bash
# ─── DocVault AI — Database Setup Script ─────────────────────
# Sets up PostgreSQL via TimescaleDB Docker container

CONTAINER_NAME="timescaledb"
DB_USER="postgres"
DB_PASS="123"
DB_NAME="micco"
DB_PORT="5433"

echo "🐘 Setting up TimescaleDB Docker container..."

# Check if container already exists
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "⚠️  Container '${CONTAINER_NAME}' already exists."

    # Start it if it's stopped
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "▶️  Starting existing container..."
        docker start "${CONTAINER_NAME}"
    else
        echo "✅ Container is already running."
    fi
else
    echo "📦 Creating new TimescaleDB container..."
    docker run -d \
        --name "${CONTAINER_NAME}" \
        -p "${DB_PORT}:5432" \
        -e POSTGRES_USER="${DB_USER}" \
        -e POSTGRES_PASSWORD="${DB_PASS}" \
        -e POSTGRES_DB="${DB_NAME}" \
        -v timescaledb_data:/var/lib/postgresql/data \
        timescale/timescaledb:latest-pg16

    echo "⏳ Waiting for PostgreSQL to be ready..."
    sleep 5

    # Wait until the database accepts connections
    for i in {1..30}; do
        if docker exec "${CONTAINER_NAME}" pg_isready -U "${DB_USER}" > /dev/null 2>&1; then
            echo "✅ PostgreSQL is ready!"
            break
        fi
        echo "   Waiting... ($i/30)"
        sleep 1
    done
fi

# Create the docvault database if it doesn't exist
echo "🗄️  Ensuring database '${DB_NAME}' exists..."
docker exec "${CONTAINER_NAME}" psql -U "${DB_USER}" -tc \
    "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'" | grep -q 1 || \
    docker exec "${CONTAINER_NAME}" psql -U "${DB_USER}" -c "CREATE DATABASE ${DB_NAME};"

echo ""
echo "════════════════════════════════════════════════"
echo "  ✅ Database Setup Complete!"
echo "════════════════════════════════════════════════"
echo "  Container:  ${CONTAINER_NAME}"
echo "  Host:       localhost:${DB_PORT}"
echo "  Database:   ${DB_NAME}"
echo "  User:       ${DB_USER}"
echo "  Password:   ${DB_PASS}"
echo ""
echo "  Connection URL:"
echo "  postgresql://${DB_USER}:${DB_PASS}@localhost:${DB_PORT}/${DB_NAME}"
echo "════════════════════════════════════════════════"
