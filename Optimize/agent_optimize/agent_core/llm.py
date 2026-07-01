import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from openai import OpenAI

from .config import ProjectContext

MOTORAI_ROOT = Path(__file__).resolve().parents[3]
if str(MOTORAI_ROOT) not in sys.path:
    sys.path.insert(0, str(MOTORAI_ROOT))

from motorai_config import get_llm_settings, load_settings


class LLMClient:
    def __init__(self, _ctx: ProjectContext) -> None:
        settings = get_llm_settings(load_settings())
        api_key = (
            str(settings.get("api_key", "") or "").strip()
            or os.getenv("AI_API_KEY")
            or os.getenv("DEEPSEEK_API_KEY")
            or os.getenv("OPENAI_API_KEY")
        )
        if not api_key:
            raise RuntimeError(
                "MotorAI LLM api_key was not found.\n"
                f"Please check {MOTORAI_ROOT / 'motorai_settings.json'} or environment variable AI_API_KEY."
            )
        self.model = (
            str(settings.get("model", "") or "").strip()
            or os.getenv("AI_MODEL")
            or os.getenv("DEEPSEEK_MODEL")
            or os.getenv("OPENAI_MODEL")
            or "deepseek-v4-flash"
        )
        self.base_url = (
            str(settings.get("base_url", "") or "").strip()
            or os.getenv("AI_BASE_URL")
            or os.getenv("DEEPSEEK_BASE_URL")
            or os.getenv("OPENAI_BASE_URL")
            or "https://api.deepseek.com"
        )
        self.client = OpenAI(api_key=api_key, base_url=self.base_url)

    def ask(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> Any:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            stream=False,
        )
        return response.choices[0].message
