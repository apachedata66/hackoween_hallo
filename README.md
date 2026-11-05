# Ghost Data Still Exists

An evidence based deletion audit tool for the college hackathon problem statement. It checks whether a request authorizes deletion, resolves current and historical identity links, reconstructs data state at the request's audit cutoff, applies the supplied retention policy, and produces evidence backed findings and safe next steps.

The decision engine is deterministic and local. It currently makes **no external model calls** and needs no API key. That keeps runs reproducible and avoids sending case data to a third party.

## Run the audit

Use Python 3.11 or newer from the repository root. Install dependencies and generate the full output:

```powershell
python -m pip install -r requirements.txt
python code/main.py run
```

This writes `output.csv` at the repository root. To check the result:

```powershell
python code/main.py validate output.csv
```

The runner stops without publishing a prediction file when evidence cannot support a safe answer. It writes a manual review summary to `evaluation/manual_review.md` in that case.

Image evidence and scanned PDF pages require local OCR tools. Install Tesseract and make `tesseract` available on `PATH`; scanned PDFs also need `pdftoppm` to render pages. On Windows, set `TESSERACT_CMD` to the executable when Tesseract is not on `PATH`, for example:

```powershell
$env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
python code/main.py run --out output.csv
```

If OCR is unavailable, image-based cases are held for manual review and no partial prediction file is written. OCR runs locally; the audit does not send evidence to an external service.

To audit the public examples or one request:

```powershell
python code/main.py run --samples --out output.samples.csv
python code/main.py run --case case_001 --out output.case.csv
```

By default, participant data is read from `dataset/`. To point at a separate dataset checkout, set `GHOSTDATA_DATASET` to its dataset directory.

## Local review UI

The React site opens with a short project landing page and a connected audit workspace. The workspace launches the same CLI engine through FastAPI, shows real request-count progress and elapsed time, validates the generated file before enabling download, masks request identifiers by default, and keeps evidence on the machine in local mode.

```powershell
python -m pip install -e ".[ui]"
python -m uvicorn ghostdata.api.app:app --app-dir src --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765` after building the frontend. For frontend development, run `npm install` and `npm run dev` from `ui/`; in another terminal start FastAPI on port 8765. Keep the service bound to localhost when reviewing case data. See [`ui/README.md`](ui/README.md) for the full workflow.

The repository includes a Vercel configuration for the static React frontend. The current FastAPI audit service needs a persistent process and participant dataset, so host it separately and set `VITE_API_BASE_URL` in Vercel to that HTTPS API origin. See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for deployment boundaries and exact settings.

## Output contract

`output.csv` has exactly these columns, in order: `case_id,deletion_status,steps_json`. It contains one row per request, sorted by `case_id`. Status is `COMPLETE`, `INCOMPLETE`, or `NOT_APPLICABLE`; each step follows the supplied finding, remediation, verification, evidence, and ordering rules. The validator checks the contract and evidence references before export.

The output file is a proposed audit result and remediation plan. Remediation steps describe future work; this tool does not execute deletions or alter source systems.

## Evaluation and package

The reproducible public sample comparison, custom cases, known benchmark limits, and final run usage figures are recorded in:

- [`evaluation/evaluation_report.md`](evaluation/evaluation_report.md)
- [`evaluation/usage_report.md`](evaluation/usage_report.md)
- [`evaluation/interview_prep.md`](evaluation/interview_prep.md) for the
  architecture walkthrough, demo sequence, measured results, and limitations.

Regenerate the public sample evaluation report from the current evidence engine and custom cases with:

```powershell
python code/evaluation/run_public_benchmark.py
```

The public sample set contains 32 cases. The report documents the current score and evidence gaps; no hidden full dataset labels are available for measuring full set accuracy.

Build the submission archive without bundling the dataset, caches, nested archives, or secrets:

```powershell
python scripts/make_zip.py
```

Build the React assets first with `npm install` and `npm run build` from `ui/`. The archive includes the runnable engine, React source and built assets, evaluation reports, configuration, and setup instructions. The generated `output.csv` is provided separately.
