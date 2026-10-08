"""Start the internal presentation service with its own provider configuration."""
import os

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="127.0.0.1", port=int(os.getenv("PRESENTATION_PORT", "8004")))
