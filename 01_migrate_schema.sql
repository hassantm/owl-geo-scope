-- OWL Knowledge Map: geo_scope classification for Australian curriculum adaptation
-- Run once on the owl DB (Pi)
-- 2026-08-25

ALTER TABLE concepts
  ADD COLUMN IF NOT EXISTS geo_scope TEXT
    CHECK (geo_scope IN ('uk_specific', 'universal', 'ambiguous')),
  ADD COLUMN IF NOT EXISTS geo_scope_confidence TEXT
    CHECK (geo_scope_confidence IN ('high', 'medium', 'low')),
  ADD COLUMN IF NOT EXISTS geo_scope_notes TEXT;

-- Index for fast filtering
CREATE INDEX IF NOT EXISTS idx_concepts_geo_scope ON concepts(geo_scope);

-- Verify
SELECT COUNT(*) AS tier3_concepts,
       COUNT(geo_scope) AS classified
FROM concepts
WHERE tier = 3;
