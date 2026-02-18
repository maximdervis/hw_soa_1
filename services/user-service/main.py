from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(
    title="User Service",
    description="Сервис управления пользователями (покупатели и продавцы)",
    version="1.0.0"
)


@app.get("/health")
async def health_check():
    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "service": "user-service"
        }
    )


@app.get("/")
async def root():
    return {"message": "User Service API"}
