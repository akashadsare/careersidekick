from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import Base, engine
from . import db_models  # noqa: F401
from .routes.candidates import router as candidate_router
from .routes.drafts import router as draft_router
from .routes.executions import router as execution_router
from .routes.jobs import router as job_router
from .routes.packages import router as package_router

app = FastAPI(title='CareerSidekick API', version='0.1.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.allowed_origin],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.on_event('startup')
def startup() -> None:
    # Keep local startup friction low while allowing migration-first deployments.
    if settings.auto_create_schema:
        Base.metadata.create_all(bind=engine)


@app.get('/health')
def health() -> dict:
    return {'status': 'ok'}


app.include_router(package_router, prefix='/api/v1/packages', tags=['packages'])
app.include_router(execution_router, prefix='/api/v1/executions', tags=['executions'])
app.include_router(candidate_router, prefix='/api/v1/candidates', tags=['candidates'])
app.include_router(job_router, prefix='/api/v1/jobs', tags=['jobs'])
app.include_router(draft_router, prefix='/api/v1/drafts', tags=['drafts'])
