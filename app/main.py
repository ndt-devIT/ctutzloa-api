import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.database import close_db, init_db
from app.routers import auth, users, suKien, diemDanh, ketQuaDiemDanh, zaloapi
from app.tasks.session_updater import auto_update_session_status


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    print("Database initialized.")

    task = asyncio.create_task(auto_update_session_status())

    yield

    task.cancel()
    await close_db()
    print("Database connection closed.")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    first_error_msg = errors[0].get("msg", "Dữ liệu đầu vào không hợp lệ")
    clean_msg = first_error_msg.replace("Value error, ", "")

    return JSONResponse(
        status_code=422,
        content={"message": clean_msg, "detail": errors},
    )


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(suKien.router)
app.include_router(diemDanh.router)
app.include_router(ketQuaDiemDanh.router)
app.include_router(zaloapi.router)


@app.get("/")
def root():
    return {"status": "OK", "message": "FastAPI is running"}