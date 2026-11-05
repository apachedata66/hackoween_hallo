# Deployment

## Vercel frontend

The Vercel configuration builds the React/Vite client and serves the static files in `ui/dist`. It also routes direct visits to `/workspace` back to the single page application.

1. Import this GitHub repository into Vercel and keep the project root at the repository root.
2. Confirm the detected build command is `npm --prefix ui ci && npm --prefix ui run build` and the output directory is `ui/dist` (both are recorded in `vercel.json`).
3. Add `VITE_API_BASE_URL` in Vercel Project Settings → Environment Variables. Set it to the HTTPS origin of the audit API, for example `https://audit-api.example.com`, with no trailing slash.
4. Redeploy after setting or changing the value. Vite embeds this public API origin during the build; it is not a secret.

The Vercel deployment hosts the user interface only. The current FastAPI service launches the CLI as a child process and keeps run state in memory; it expects the participant dataset on local or mounted storage. It is not a Vercel serverless function. Run FastAPI as a separate, persistent service with the participant dataset available at `GHOSTDATA_DATASET` (or under the repository's `dataset/` directory).

Set `GHOSTDATA_CORS_ORIGINS` on the API service to a comma-separated list of exact Vercel origins, including the production origin and any preview origins that should be allowed. Do not use `*` for a deployed service. The API does not use cookies or browser credentials.

The browser sends audit requests and evidence queries to the configured API origin. Deploy only fictional challenge data and use hosting controls appropriate to the sensitivity of any data placed there. For a local demo, leave `VITE_API_BASE_URL` unset and run the bundled FastAPI service on `127.0.0.1`.

## Local production-style preview

From the repository root:

```powershell
Push-Location ui
npm ci
npm run build
Pop-Location
python -m pip install -e ".[ui]"
python -m uvicorn ghostdata.api.app:app --app-dir src --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765`. The FastAPI application serves the built React client and the audit API from the same origin.
