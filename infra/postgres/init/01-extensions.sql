-- Extensions required by Nyaya.
--   vector    : dense embedding storage + ANN search (retrieval spine)
--   pg_trgm   : trigram similarity, used for fuzzy clause-reference matching
--   uuid-ossp : primary key generation
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- English text-search configuration used for the lexical half of hybrid retrieval.
-- Declared here so that generated tsvector columns resolve identically in every environment.
ALTER DATABASE nyaya SET default_text_search_config = 'pg_catalog.english';
