# Helpdesk frontend

React + TypeScript + Vite. See [the project README](../README.md) for complete setup, architecture, APIs and demo instructions.

From this directory:

```powershell
npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort
npm.cmd run lint
npm.cmd run build
```

The API defaults to http://127.0.0.1:8000. `VITE_API_BASE_URL` may change only the backend address; never place credentials in frontend environment variables.

The existing TypeScript 6.0.3, minimatch 11.0.3 override and npm lockfile are retained.
