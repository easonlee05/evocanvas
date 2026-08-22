import os

try:
    import dotenv
    dotenv.load_dotenv = lambda *args, **kwargs: None
except ImportError:
    pass

for key in ["API_KEY", "BASE_URL", "LLM_MODEL", "CRS_OAI_KEY"]:
    if key in os.environ:
        del os.environ[key]
    os.environ[key] = ""
