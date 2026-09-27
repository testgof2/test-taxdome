#!/bin/sh
set -eu

psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=test_db="$POSTGRES_TEST_DB" \
  --set=db_user="$POSTGRES_USER" <<'SQL'
SELECT format('CREATE DATABASE %I OWNER %I', :'test_db', :'db_user')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'test_db')\gexec
SQL
