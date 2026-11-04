# Evidence Loader Reliability Audit

## Scope and method

Reviewed the participant-facing evidence formats and the loader path used by
the audit engine: JSON records, operational logs, PDF/image/text extraction,
SQL snapshots, the evidence manifest, and document cache behavior. Fixtures in
`tests/test_evidence_loader_reliability.py` are small fictional examples and do
not copy dataset content or encode challenge case IDs.

## Confirmed defect and fix

The JSON record parser preferred an enclosing snapshot timestamp over an
explicit timestamp on a nested record. For example, a snapshot captured after
an audit cutoff could contain a record whose own observation time was before
the cutoff; the parser incorrectly assigned the later snapshot time. The
reverse ordering could also happen, causing post-cutoff evidence to look
earlier. The parser now prefers the record's own timestamp and inherits the
nearest enclosing timestamp only when the record has no explicit timestamp.
Malformed explicit timestamps now raise `LoaderError` instead of silently
falling back to an inherited time, allowing the evidence pipeline to surface a
warning and skip unsafe time interpretation.

## Regression coverage

The fictional tests cover JSON source provenance, parent timestamp inheritance,
record timestamp precedence, nullable identifier fields, malformed timestamps,
log warning behavior, missing documents, corrupt cache recovery, SQL replica
and source IDs, escaped JSON values, and malformed SQL. Existing tests also
cover path traversal protection and deterministic OCR-unavailable behavior.

## Public sample evaluation

Command:

```powershell
$env:GHOSTDATA_DATASET = "<official dataset directory>"
python code/main.py run --samples --out tmp-samples.csv
```

The runner safely held the three cases with no linked resource evidence:
`case_01`, `case_02`, and `case_04`. To measure supported-case metrics without
fabricating rows, the evaluation harness ran the shared provider and planner,
excluded only outcomes explicitly flagged for manual review, and scored the
remaining 29 results with:

```powershell
python code/evaluation/score_samples.py --pred .pytest-tmp/supported-samples.csv --show 0
```

Results were unchanged from the recorded baseline: status accuracy `0.9062`,
step precision `0.9509`, step recall `0.8201`, step F1 `0.8807`, and sequence
accuracy `0.2188` (29 of 32 samples scored). This loader fix did not change
public-sample predictions; it corrects timestamp precedence for evidence
records that explicitly carry their own time. No hidden-answer performance
claim is made.

## Remaining limits

Image and scanned-PDF extraction still depends on locally available Tesseract;
when unavailable or unsuccessful, the loader preserves a warning instead of
silently treating the source as readable text. The three manual-review cases
remain unresolved by this loader-only work because resource linkage belongs to
the evidence-pipeline workstream.
