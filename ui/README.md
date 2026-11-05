# React review interface

The local interface uses React, TypeScript, and Vite. FastAPI serves the production build and runs the existing CLI as a background process. The browser does not implement identity resolution, policy, or audit decisions.

## Run the built interface

From the repository root, install the optional Python dependencies and build the frontend once:

```powershell
python -m pip install -e ".[ui]"
Push-Location ui; npm install; npm run build; Pop-Location
python -m uvicorn ghostdata.api.app:app --app-dir src --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765`. Configure a dataset outside the app using `GHOSTDATA_DATASET` if the repository does not contain `dataset/`.

## Develop the frontend

Start FastAPI on `127.0.0.1:8765` in one terminal, then run this in `ui/`:

```powershell
npm install
npm run dev
```

Vite proxies API calls to FastAPI. Open the address printed by Vite. Use `npm run build` to create the static bundle at `ui/dist/`.

Runs show actual CLI progress. A failed or manual-review-required run cannot be exported. Case identifiers are masked by default. The evidence drawer enforces the case cutoff, masks identifiers in excerpts, and labels activity records as claims. When a cited image is available by the case cutoff, the reviewer can explicitly open the original image; the disclosure warns that it may contain direct identifiers. The local API serves that image only for the cited case and evidence ID.
