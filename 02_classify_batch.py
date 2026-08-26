"""
OWL geo_scope classifier — batch pass over Tier 3 concepts
Classifies each term as: uk_specific | universal | ambiguous

Usage:
    python 02_classify_batch.py [--dry-run] [--limit N]

Requirements:
    pip install anthropic psycopg2-binary python-dotenv
    ANTHROPIC_API_KEY in environment

Output: writes geo_scope, geo_scope_confidence, geo_scope_notes back to the owl DB.
"""

import os
import json
import time
import argparse
import psycopg2
import anthropic

# ── Config ─────────────────────────────────────────────────────────────────────

DB_DSN = "dbname=owl"          # adjust if needed
BATCH_SIZE = 20                # concepts per API call
SLEEP_BETWEEN_BATCHES = 1.0   # seconds — stay polite to the API

SYSTEM_PROMPT = """You are classifying educational vocabulary terms from a UK KS2 (ages 7–11) humanities curriculum.

Your task: determine whether each term is specific to a UK/British context, or whether it is a universal concept that happens to appear in the UK curriculum.

This classification is needed because the curriculum is being adapted for Australian schools, and we need to identify which terms are too UK-specific to translate directly and will need replacement or supplementation.

For each term, classify as ONE of:
- uk_specific: The term refers to something uniquely or primarily British/English — a specific UK historical event, figure, place, institution, law, or cultural practice that would not be taught in an Australian equivalent curriculum. Examples: Magna Carta, Houses of Parliament, the Blitz, enclosure acts, Victorian workhouses.
- universal: The term is a concept taught across many national curricula and not tied to UK context, even if the UK curriculum uses it. Examples: democracy, migration, empire, monastery, erosion, trade route, persecution.
- ambiguous: The term could go either way depending on how it is taught, or it refers to something with both universal and UK-specific dimensions. Examples: Commonwealth (has a specific UK meaning but also a universal one), parish (UK church administration but also broader Christian concept).

Return a JSON array, one object per term, with these fields:
- concept_id: integer (echo back unchanged)
- geo_scope: "uk_specific" | "universal" | "ambiguous"
- confidence: "high" | "medium" | "low"
- notes: one sentence explaining the classification (max 120 chars)

Return ONLY valid JSON. No preamble, no markdown fences."""

USER_PROMPT_TEMPLATE = """Classify these {n} terms:

{terms_json}"""


def get_concepts(conn, limit=None):
    """Fetch unclassified Tier 3 concepts with definitions."""
    sql = """
        SELECT concept_id, term, subject_area, definition
        FROM concepts
        WHERE tier = 3
          AND geo_scope IS NULL
          AND definition IS NOT NULL
        ORDER BY subject_area, concept_id
    """
    if limit:
        sql += f" LIMIT {limit}"
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()


def classify_batch(client, batch):
    """Send a batch of concepts to Claude for classification."""
    terms_json = json.dumps([
        {
            "concept_id": row[0],
            "term": row[1],
            "subject_area": row[2] or "unclassified",
            "definition": row[3]
        }
        for row in batch
    ], indent=2)

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": USER_PROMPT_TEMPLATE.format(
                n=len(batch), terms_json=terms_json
            )}
        ]
    )

    raw = message.content[0].text.strip()
    # Strip markdown fences if model adds them anyway
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


def write_results(conn, results, dry_run=False):
    """Write classification results back to DB."""
    if dry_run:
        for r in results:
            print(f"  [{r['geo_scope']:12s} / {r['confidence']:6s}] {r['concept_id']}: {r.get('notes','')}")
        return

    with conn.cursor() as cur:
        for r in results:
            cur.execute("""
                UPDATE concepts
                SET geo_scope = %s,
                    geo_scope_confidence = %s,
                    geo_scope_notes = %s
                WHERE concept_id = %s
            """, (r['geo_scope'], r['confidence'], r.get('notes'), r['concept_id']))
    conn.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print results, don't write to DB")
    parser.add_argument("--limit", type=int, default=None, help="Process only N concepts (for testing)")
    args = parser.parse_args()

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    conn = psycopg2.connect(DB_DSN)

    concepts = get_concepts(conn, limit=args.limit)
    print(f"Found {len(concepts)} unclassified Tier 3 concepts")

    total_classified = 0
    for i in range(0, len(concepts), BATCH_SIZE):
        batch = concepts[i:i + BATCH_SIZE]
        print(f"Batch {i//BATCH_SIZE + 1}: concepts {i+1}–{i+len(batch)} ...", end=" ", flush=True)

        try:
            results = classify_batch(client, batch)
            write_results(conn, results, dry_run=args.dry_run)
            total_classified += len(results)
            print(f"✓ ({len(results)} classified)")
        except Exception as e:
            print(f"✗ ERROR: {e}")
            # Continue with next batch rather than dying
            continue

        if i + BATCH_SIZE < len(concepts):
            time.sleep(SLEEP_BETWEEN_BATCHES)

    conn.close()
    print(f"\nDone. {total_classified}/{len(concepts)} concepts classified.")


if __name__ == "__main__":
    main()
