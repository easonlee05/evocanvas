# 强制全局将 load_dotenv 设为 no-op，并彻底清空所有 LLM 相关环境变量，确保所有单测始终平滑降级于本地 mock
import os
import dotenv
dotenv.load_dotenv = lambda *args, **kwargs: None

for key in ["API_KEY", "BASE_URL", "LLM_MODEL", "CRS_OAI_KEY"]:
    if key in os.environ:
        del os.environ[key]
    os.environ[key] = ""
