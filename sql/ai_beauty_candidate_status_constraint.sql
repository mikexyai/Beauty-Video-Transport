-- AI Beauty candidate_status CHECK constraint migration.
-- Source of truth for allowed values: scripts/ai_beauty/state.py ALL_CANDIDATE_STATUSES.
-- Constraint name: ai_beauty_candidates_status_check.

BEGIN;

-- 1) Audit historical values before applying the constraint.
-- Expected result: zero rows. If any rows are returned, stop and remediate them explicitly.
SELECT candidate_status, count(*) AS row_count
FROM beauty.ai_beauty_candidates
WHERE candidate_status NOT IN (
    'new',
    'archived',
    'batch_selected',
    'screened_out',
    'uploaded',
    'archive_pruned',
    'failed',
    'downloaded',
    'approved'
)
GROUP BY candidate_status
ORDER BY candidate_status;

-- 2) Apply/enforce the CHECK constraint.
ALTER TABLE beauty.ai_beauty_candidates
DROP CONSTRAINT IF EXISTS ai_beauty_candidates_status_check;

ALTER TABLE beauty.ai_beauty_candidates
ADD CONSTRAINT ai_beauty_candidates_status_check
CHECK (candidate_status IN (
    'new',
    'archived',
    'batch_selected',
    'screened_out',
    'uploaded',
    'archive_pruned',
    'failed',
    'downloaded',
    'approved'
));

-- 3) Verify the installed constraint definition.
SELECT conname, pg_get_constraintdef(c.oid) AS definition
FROM pg_constraint c
JOIN pg_class t ON t.oid = c.conrelid
JOIN pg_namespace n ON n.oid = t.relnamespace
WHERE n.nspname = 'beauty'
  AND t.relname = 'ai_beauty_candidates'
  AND c.contype = 'c'
  AND conname = 'ai_beauty_candidates_status_check';

COMMIT;

-- Rollback contract:
-- Run this only if the constraint must be removed while preserving existing rows.
-- BEGIN;
-- ALTER TABLE beauty.ai_beauty_candidates
-- DROP CONSTRAINT IF EXISTS ai_beauty_candidates_status_check;
-- COMMIT;
