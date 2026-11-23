# Video Converter

A small web app for combining video files you own or are authorised to process into one MP4.

## Project structure

- `index.html` — static frontend for Vercel
- `backend/main.py` — FastAPI upload/merge API
- `backend/Dockerfile` — Railway container with FFmpeg installed

## Deploy backend to Railway

1. Push this repository to GitHub.
2. In Railway, create a new project and deploy from the GitHub repository.
3. Set the Railway service's **Root Directory** to `/backend`.
4. Railway should detect the Dockerfile and build it.
5. Generate a public domain in the service's Networking settings.
6. Test `https://YOUR-RAILWAY-DOMAIN/health`; it should return `{"status":"ok"}`.

## Deploy frontend to Vercel

1. Import the same GitHub repository into Vercel.
2. Keep the project root as `/`.
3. Deploy the project.
4. In `index.html`, replace `https://YOUR-RAILWAY-APP.up.railway.app` in `API_BASE` with your Railway public domain.
5. Commit and push the change; Vercel will redeploy.

## Important starter limitations

- Uploads are limited to 20 files and 500 MB total per request.
- The initial merge filter expects every video to have an audio stream when merging multiple files. This is a known MVP limitation; next iteration should add silent audio tracks for videos without audio.
- Processing is synchronous and uses temporary local disk. For larger jobs, add a job queue and object storage.
- This app does not download from YouTube. Use videos you own or are authorised to process.
- Add authentication, rate limiting, stronger file validation, and cost controls before making the service public.
