from fastapi import FastAPI

app = FastAPI(title="Envelo API Gateway")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
