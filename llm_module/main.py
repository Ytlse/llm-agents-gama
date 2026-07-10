"""
main.py — Point d'entrée uvicorn (compat docker-compose : `llm_module.main:app`).

L'application est construite par la fabrique create_app() (api/app.py) :
composition explicite des dépendances, reset RPM dans le lifespan.
"""

from llm_module.api.app import create_app

app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("llm_module.main:app", host="0.0.0.0", port=8000, reload=True)
