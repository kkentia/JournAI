#-------------------------FastAPI app--------------------------------

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import multiprocessing
from llama_cpp import Llama
import logging


from db import get_or_create_session_id, init_db, close_db, create_tables
from endpoints.chat import chat_router
from endpoints.user import user_router
from endpoints.mood import mood_router
from endpoints.metrics import metrics_router
from endpoints.notes import notes_router
from endpoints.chat import entries_router
from endpoints.sentiment_analysis import analysis_router
from endpoints.themeriver import themeriver_router



from sessionMemory import sessionMemory, session_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # load windows model
#---------------------------------------------------------
    # app.state.llm = Llama(
    #     model_path="./model/DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf",
    #     n_ctx=4096,
    #     n_threads=min(multiprocessing.cpu_count(), 6),
    #     f16_kv=True,
    #     use_mlock=True,
    #     n_gpu_layers=-1,
    #     n_batch=512,
    # )
 #---------------------------------------------------------
    # load mac model (optimized for M1 performance)
    try:
        app.state.llm = Llama(
            model_path="./model/mistral-7b-instruct-v0.1.Q6_K_M.gguf",
            n_ctx=4096,
            n_threads=min(multiprocessing.cpu_count(), 6),
            f16_kv=True,
            use_mlock=True,
            n_gpu_layers=-1,
            n_batch=512, #256
            use_metal=False
        )
        logging.info("Llama model loaded successfully.")
    except Exception as e:
        logging.warning(f"Failed to load Llama model: {e}")
        app.state.llm = None

    #  DB init
    app.state.db = init_db()
    db = app.state.db                     
    db.execute("PRAGMA foreign_keys = ON")  # enable foreign key (off by default for sqlite)
    create_tables(db)

    app.state.session_id = get_or_create_session_id(db)
    
    yield

    close_db(db)

app = FastAPI(lifespan=lifespan, debug=True)
app.include_router(session_router)
app.state.journal = sessionMemory()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# routers
app.include_router(chat_router)
app.include_router(user_router)
app.include_router(mood_router)
app.include_router(metrics_router) # for manual (user) input of metrics
app.include_router(notes_router)
app.include_router(entries_router)
app.include_router(analysis_router) # for AI input of metrics
app.include_router(themeriver_router)

