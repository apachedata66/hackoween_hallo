# Local audit review UI

This is a local Streamlit front end for the existing Ghost Data CLI. It never computes or edits a verdict. The CLI and validator remain the source of truth.

## Setup and launch

From the repository root, install the optional UI extra and launch on localhost:

```powershell
python -m pip install -e ".[ui]"
$env:GHOSTDATA_DATASET = "C:\path\to\official\dataset"
streamlit run ui/app.py --server.address 127.0.0.1
```

The dataset path must contain the participant-facing files expected by the CLI. The browser UI offers the full dataset, public sample requests, or an uploaded request CSV.

## Interaction

- Start an audit and watch actual CLI progress, elapsed time, warnings, and completion or failure output.
- When the CLI exits successfully, the UI runs the existing output validator. Download stays unavailable unless validation passes.
- Search cases by ID or email. Email identifiers are masked by default; use the explicit local-only checkbox to reveal them.
- Review audit cutoff, reported workflow status, request text, and ordered findings, future actions, and verifications. Evidence IDs are shown separately from proposed work.
- Open the evidence drawer to inspect source metadata, activity claims, and identity-history references. File excerpts load only on request, match the selected subject or resource, and mask participant-facing identity values. Evidence after the audit cutoff stays hidden.
- Download the exact validated output bytes. No verdict or step is recomputed in the UI.

Request and output files are processed by the local Streamlit process. Keep the server bound to localhost when handling case data.

## Current boundary

The UI uses the existing CLI as a subprocess and reflects its output. It does not add an evidence engine, open source evidence snippets, or reinterpret audit warnings. If a case needs manual review or the CLI fails validation, the UI shows the failure and does not enable export.
