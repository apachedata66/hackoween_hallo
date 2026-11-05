# Deployment

## Vercel frontend

The Vercel project serves the React/Vite client as a static site. The repository-root `vercel.json` explicitly selects Vite, installs the `ui/` dependencies, builds the app, and serves `ui/dist`. It also routes direct visits to `/workspace` back to the single page application.

1. Import this GitHub repository into Vercel. Set **Root Directory** to `.` (the repository root) and **Framework Preset** to **Vite**.
2. Leave the install, build, and output settings controlled by `vercel.json`: `npm --prefix ui ci`, `npm --prefix ui run build`, and `ui/dist`.
3. Host the FastAPI audit service separately on a persistent Python web service. This app launches the CLI as a child process, tracks active run progress in process memory, and needs the participant dataset at runtime. Vercel supports FastAPI, but this current process and state model needs a persistent API host; selecting FastAPI as the Vercel project preset would also deploy the API in place of this React interface.
4. Add `VITE_API_BASE_URL` in Vercel Project Settings → Environment Variables. Set it to the HTTPS origin of the audit API, for example `https://audit-api.example.com`, with no trailing slash.
5. Set `GHOSTDATA_DATASET` on the API service to the participant dataset directory. Redeploy the frontend after changing `VITE_API_BASE_URL`; Vite embeds it during the build, and it is not a secret.

If the Vite site loads but the audit controls report that the API is unreachable, the frontend deployment succeeded; the API URL, API service, dataset path, or CORS origin still needs configuration. The API must expose `/api/health` over HTTPS before the workspace can run audits.

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
python -m uvicorn ghostdata.api.app:app --app-dir code --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765`. The FastAPI application serves the built React client and the audit API from the same origin.
