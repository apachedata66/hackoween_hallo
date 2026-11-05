# React review interface

The local interface uses React, TypeScript, and Vite. FastAPI serves the production build and runs the existing CLI as a background process. The browser does not implement identity resolution, policy, or audit decisions.

The root URL is an editorial project landing page. The **Open audit workspace** action and `/workspace` route lead to the same React review interface and same FastAPI API; they do not use a separate demo implementation.

On the overview, **Open validated output** loads the repository's existing `output.csv` only after revalidating it against the current participant dataset. This opens the case register immediately for a presentation. **Audit all requests** runs the engine again; scanned evidence requires Tesseract to be available through `TESSERACT_CMD` or `PATH`.

## Run the built interface

From the repository root, install the optional Python dependencies and build the frontend once:

```powershell
python -m pip install -e ".[ui]"
Push-Location ui; npm install; npm run build; Pop-Location
python -m uvicorn ghostdata.api.app:app --app-dir code --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765`. Configure a dataset outside the app using `GHOSTDATA_DATASET` if the repository does not contain `dataset/`.

## Develop the frontend

Start FastAPI on `127.0.0.1:8765` in one terminal, then run this in `ui/`:

```powershell
npm install
npm run dev
```

Vite proxies API calls to FastAPI. Open the address printed by Vite. Use `npm run build` to create the static bundle at `ui/dist/`.

## Vercel frontend

`vercel.json` builds and hosts the static React client. Configure `VITE_API_BASE_URL` as the HTTPS origin for a separately hosted FastAPI service. Add the deployed site origins to that service's `GHOSTDATA_CORS_ORIGINS`. The current subprocess and in-memory run implementation must stay on a persistent API host; it is not a Vercel serverless function. See [`../docs/DEPLOYMENT.md`](../docs/DEPLOYMENT.md).

Runs show actual CLI progress. A failed or manual-review-required run cannot be exported. Case identifiers are masked by default. The evidence drawer enforces the case cutoff, masks identifiers in excerpts, and labels activity records as claims. When a cited image is available by the case cutoff, the reviewer can explicitly open the original image; the disclosure warns that it may contain direct identifiers. The local API serves that image only for the cited case and evidence ID.

The overview checks the participant dataset and, after a validated run, summarizes verdict counts, highlights incomplete cases with recreation risks, and links recurring finding systems to filtered cases. The case register supports status and system filters, live search, risk/date/ID sorting, 25-row paging, and a masked CSV export of the current filtered view. Individual cases also provide a masked JSON handoff report and a browser-local checklist for proposed remediation and future verification. Checklist marks are self-attested and never alter the result or source systems; the validated full output remains a separate download.
