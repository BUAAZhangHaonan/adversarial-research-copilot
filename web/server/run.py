import uvicorn

from arc_arena.config import load_config
from arc_arena.app import create_app

cfg = load_config()
app = create_app(cfg)

if __name__ == "__main__":
    uvicorn.run(app, host=cfg.host, port=cfg.port, log_level="info")
