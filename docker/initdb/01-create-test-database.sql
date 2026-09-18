-- Create the integration-test database alongside the application one (D-04).
--
-- The official postgres image runs everything in /docker-entrypoint-initdb.d
-- ONLY when it starts against an empty data directory. On a volume that already
-- holds a cluster this file is skipped in silence, so adding it to a project
-- someone has already started leaves taskmanager_test missing and every
-- integration test failing with `database "taskmanager_test" does not exist`.
-- The documented reset is `docker compose down -v`, which discards the named
-- volume and makes the next `up` run this script again (D-14).
--
-- PostgreSQL has no CREATE DATABASE ... IF NOT EXISTS, and CREATE DATABASE
-- cannot run inside psql's implicit transaction with a conditional around it.
-- The standard escape is to have the server compose the statement as text and
-- hand it back to psql with \gexec, which executes it only when the SELECT
-- returned a row.
SELECT 'CREATE DATABASE taskmanager_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'taskmanager_test')\gexec
