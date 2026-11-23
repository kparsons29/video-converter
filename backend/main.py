import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

app = FastAPI(title="Video Converter API")

frontend_origin = os.getenv("FRONTEND_ORIGIN", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if frontend_origin == "*" else [frontend_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

MAX_FILES = 20
MAX_TOTAL_BYTES = 500 * 1024 * 1024  # 500 MB starter limit
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/merge")
def merge_videos(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="Upload at least one video.")
    if len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_FILES} files per merge.")

    workdir = Path(tempfile.mkdtemp(prefix="video-merge-"))
    output_path = workdir / "combined-video.mp4"
    input_paths = []
    total_bytes = 0

    try:
        for index, upload in enumerate(files):
            suffix = Path(upload.filename or "").suffix.lower()
            if suffix not in ALLOWED_EXTENSIONS:
                raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix or 'unknown'}")
            destination = workdir / f"input_{index:03d}{suffix}"
            with destination.open("wb") as target:
                while True:
                    chunk = upload.file.read(1024 * 1024)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > MAX_TOTAL_BYTES:
                        raise HTTPException(status_code=413, detail="Combined upload limit is 500 MB.")
                    target.write(chunk)
            input_paths.append(destination)

        # Re-encode to a consistent H.264/AAC MP4 output so mixed input formats
        # are more likely to combine successfully.
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        for path in input_paths:
            command += ["-i", str(path)]

        if len(input_paths) == 1:
            command += [
                "-map", "0:v:0", "-map", "0:a?",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
                str(output_path),
            ]
        else:
            streams = "".join(f"[{i}:v:0][{i}:a:0] " for i in range(len(input_paths)))
            # The concat filter requires audio on every input. If some files
            # lack audio, FFmpeg may reject them; the API reports a useful error.
            command += [
                "-filter_complex",
                "".join(f"[{i}:v:0]setpts=PTS-STARTPTS[v{i}];[{i}:a:0]asetpts=PTS-STARTPTS[a{i}];" for i in range(len(input_paths)))
                + "".join(f"[v{i}][a{i}]" for i in range(len(input_paths)))
                + f"concat=n={len(input_paths)}:v=1:a=1[v][a]",
                "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
                str(output_path),
            ]

        result = subprocess.run(command, capture_output=True, text=True, timeout=1800)
        if result.returncode != 0 or not output_path.exists():
            detail = (result.stderr or "FFmpeg could not process these files.")[-1800:]
            raise HTTPException(status_code=422, detail=detail)

        return FileResponse(
            output_path,
            media_type="video/mp4",
            filename="combined-video.mp4",
            background=BackgroundTask(shutil.rmtree, workdir, ignore_errors=True),
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Video processing timed out. Try smaller or shorter files.")
    except HTTPException:
        shutil.rmtree(workdir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(workdir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Processing failed: {exc}")
