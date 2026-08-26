-- OWL Knowledge Map: UK-specific Tier 3 vocab — recurrence map
-- Run after 02_classify_batch.py has populated geo_scope
-- Shows where each UK-specific term is introduced and where it recurs
-- 2026-08-25

-- ── Summary: count of UK-specific terms by subject ──────────────────────────
SELECT
    subject_area,
    COUNT(*) AS uk_specific_terms
FROM concepts
WHERE tier = 3
  AND geo_scope = 'uk_specific'
GROUP BY subject_area
ORDER BY uk_specific_terms DESC;


-- ── Main recurrence map ───────────────────────────────────────────────────────
-- For each UK-specific term: every unit where it appears, ordered chronologically
-- is_introduction = 1 flags where the term is first formally introduced
SELECT
    c.concept_id,
    c.term,
    c.subject_area,
    c.geo_scope_confidence,
    c.geo_scope_notes,
    u.subject,
    u.year,
    u.term        AS curriculum_term,
    u.unit,
    o.slide_number,
    o.is_introduction,
    o.term_in_context
FROM concepts c
JOIN occurrences o  ON c.concept_id = o.concept_id
JOIN units u        ON o.unit_id    = u.unit_id
WHERE c.tier = 3
  AND c.geo_scope = 'uk_specific'
ORDER BY
    c.subject_area,
    c.term,
    u.year,
    u.term,
    o.slide_number;


-- ── Knock-on map: downstream concepts connected via edges ────────────────────
-- If a UK-specific concept has edges to other concepts, those may also need review
-- even if not themselves UK-specific
WITH uk_occurrences AS (
    SELECT o.occurrence_id, c.term AS uk_term, c.concept_id AS uk_concept_id
    FROM concepts c
    JOIN occurrences o ON c.concept_id = o.concept_id
    WHERE c.tier = 3 AND c.geo_scope = 'uk_specific'
),
downstream AS (
    -- Concepts that are pointed TO from a UK-specific occurrence
    SELECT
        uk.uk_term,
        uk.uk_concept_id,
        e.edge_type,
        e.edge_nature,
        o2.occurrence_id AS downstream_occurrence_id,
        c2.concept_id   AS downstream_concept_id,
        c2.term         AS downstream_term,
        c2.geo_scope    AS downstream_geo_scope,
        u2.subject,
        u2.year,
        u2.term         AS curriculum_term,
        u2.unit
    FROM uk_occurrences uk
    JOIN edges e          ON e.from_occurrence = uk.occurrence_id
    JOIN occurrences o2   ON e.to_occurrence   = o2.occurrence_id
    JOIN concepts c2      ON o2.concept_id      = c2.concept_id
    JOIN units u2         ON o2.unit_id         = u2.unit_id
)
SELECT *
FROM downstream
ORDER BY uk_term, year, curriculum_term, unit;


-- ── Ambiguous terms: need human review ───────────────────────────────────────
SELECT
    concept_id,
    term,
    subject_area,
    geo_scope_confidence,
    geo_scope_notes,
    definition
FROM concepts
WHERE tier = 3
  AND geo_scope = 'ambiguous'
ORDER BY subject_area, term;
