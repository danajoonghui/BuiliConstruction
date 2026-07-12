\set ON_ERROR_STOP on

-- Run once against the dedicated BUILI database as the RDS bootstrap/admin
-- role. Supply passwords through protected psql variables, never command-line
-- literals or committed files:
--   psql ... --set=api_password=... --set=worker_password=... --set=migrator_password=...
\if :{?api_password}
\else
  \error 'api_password psql variable is required'
\endif
\if :{?worker_password}
\else
  \error 'worker_password psql variable is required'
\endif
\if :{?migrator_password}
\else
  \error 'migrator_password psql variable is required'
\endif

SELECT format('CREATE ROLE buili_api LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT', :'api_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'buili_api') \gexec
SELECT format('CREATE ROLE buili_worker LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT', :'worker_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'buili_worker') \gexec
SELECT format('CREATE ROLE buili_migrator LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT', :'migrator_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'buili_migrator') \gexec

GRANT CONNECT ON DATABASE :DBNAME TO buili_api, buili_worker, buili_migrator;
GRANT USAGE, CREATE ON SCHEMA public TO buili_migrator;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- Deliberately never grant buili_worker to buili_api. RLS worker bypass checks
-- PostgreSQL current_user, not a caller-controlled session setting.
REVOKE buili_worker FROM buili_api;
