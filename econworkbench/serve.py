"""Container entrypoint with a platform-provided PORT and one session owner."""
import os
import uvicorn


if __name__ == '__main__':
    uvicorn.run('econworkbench.api:app', host='0.0.0.0',
                port=int(os.environ.get('PORT', '8000')), workers=1,
                access_log=False, limit_concurrency=64, timeout_keep_alive=5)
