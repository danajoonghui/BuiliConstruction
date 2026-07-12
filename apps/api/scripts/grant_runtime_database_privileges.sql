\set ON_ERROR_STOP on

-- Run after every migration as buili_migrator (or the bootstrap role).
GRANT USAGE ON SCHEMA public TO buili_api, buili_worker;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO buili_api, buili_worker;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO buili_api, buili_worker;

ALTER DEFAULT PRIVILEGES FOR ROLE buili_migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO buili_api, buili_worker;
ALTER DEFAULT PRIVILEGES FOR ROLE buili_migrator IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO buili_api, buili_worker;

REVOKE CREATE ON SCHEMA public FROM buili_api, buili_worker;
REVOKE buili_worker FROM buili_api;
