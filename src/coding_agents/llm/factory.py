from coding_agents.config import Config
from coding_agents.llm.base import LLMClientProtocol
from coding_agents.llm.openrouter_client import OpenRouterClient
from coding_agents.llm.yandexgpt_client import YandexGPTClient


def create_llm_client(cfg: Config) -> LLMClientProtocol:
    if cfg.llm_provider == "yandexgpt":
        if not cfg.yc_folder_id:
            raise ValueError("YC_FOLDER_ID is required for YandexGPT")
        auth = cfg.yc_iam_token or cfg.llm_api_key
        if not auth:
            raise ValueError("YC_IAM_TOKEN or YC_API_KEY is required for YandexGPT")
        return YandexGPTClient(
            folder_id=cfg.yc_folder_id,
            api_key=cfg.llm_api_key if not cfg.yc_iam_token else "",
            iam_token=cfg.yc_iam_token,
        )
    if not cfg.llm_api_key:
        raise ValueError("OPENROUTER_API_KEY is required for OpenRouter")
    return OpenRouterClient(api_key=cfg.llm_api_key, model=cfg.llm_model)
