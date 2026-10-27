import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

conn = psycopg2.connect(host='127.0.0.1', port=5433, user='postgres', dbname='postgres')
conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
cursor = conn.cursor()

# Check existing databases
cursor.execute("SELECT 1 FROM pg_database WHERE datname='ever_near'")
exists = cursor.fetchone()
if not exists:
    cursor.execute("CREATE DATABASE ever_near")
    print("Database 'ever_near' created successfully on PostgreSQL 18 (port 5433)!")
else:
    print("Database 'ever_near' already exists on port 5433.")

cursor.close()
conn.close()

# Verify connection to ever_near
conn_app = psycopg2.connect(host='127.0.0.1', port=5433, user='postgres', dbname='ever_near')
print("Successfully connected to 'ever_near' database on PostgreSQL 18! Server version:", conn_app.server_version)
conn_app.close()
