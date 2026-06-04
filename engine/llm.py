import json
import time
from typing import List, Dict, Any, Optional
import litellm
from litellm import completion

class LLMAdapter:
    """Adapter for interacting with various LLMs (OpenAI, Gemini, Anthropic, Ollama, etc.)"""
    
    def __init__(self, provider: str, api_key: str, model_name: str = ""):
        self.provider = provider
        self.api_key = api_key
        # For litellm, model strings are usually prefixed like "gemini/gemini-pro" or "gpt-4"
        self.model = model_name or self._get_default_model(provider)
        
        # Set API key in litellm depending on provider
        if provider == "openai":
            litellm.api_key = api_key
        elif provider == "gemini":
            litellm.gemini_api_key = api_key
        elif provider == "anthropic":
            litellm.anthropic_api_key = api_key
        # Add other providers as needed

    def _get_default_model(self, provider: str) -> str:
        defaults = {
            "openai": "gpt-4-turbo",
            "gemini": "gemini/gemini-2.0-flash",
            "anthropic": "claude-3-opus-20240229",
            "ollama": "ollama/llama3"
        }
        return defaults.get(provider.lower(), "gpt-3.5-turbo")

    def generate_test_instructions(self, manual_steps: str) -> List[str]:
        """
        Takes raw manual test steps (e.g. from CSV/Excel) and converts them 
        into an array of QA Platform instructions.
        """
        system_prompt = (
            "You are an expert QA Automation Engineer. Convert the following manual test cases into "
            "a JSON array of test steps for our execution engine. "
            "Each step must be a JSON object with keys: "
            "'action' (one of: navigate, click, fill, select, assert_text, check, uncheck, press, wait), "
            "'selector' (Playwright locator like 'text=Foo' or 'get_by_label(\"Bar\")', or empty if action is navigate), "
            "'value' (string to fill or select, or URL if action is navigate), "
            "'description' (natural language description of the step).\n\n"
            "Return ONLY a valid JSON array of objects, nothing else."
        )
        
        # Retry up to 3 times with exponential backoff for 429 rate limits
        retry_delays = [10, 30, 60]
        last_error = None
        for attempt, delay in enumerate(retry_delays, start=1):
            try:
                response = completion(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": manual_steps}
                    ],
                    api_key=self.api_key
                )
                
                content = response.choices[0].message.content.strip()
                # Strip any markdown fences (```json ... ``` or ``` ... ```)
                if content.startswith("```"):
                    content = content.split("\n", 1)[-1]  # drop opening fence line
                if content.endswith("```"):
                    content = content.rsplit("```", 1)[0]  # drop closing fence
                    
                instructions = json.loads(content.strip())
                if not isinstance(instructions, list):
                    raise ValueError("LLM did not return a list")
                    
                return instructions
                
            except Exception as e:
                last_error = e
                err_str = str(e).lower()
                # Retry on quota/rate-limit errors
                if "429" in err_str or "quota" in err_str or "rate" in err_str:
                    if attempt < len(retry_delays):
                        print(f"[LLM] Rate limited (attempt {attempt}). Retrying in {delay}s...")
                        time.sleep(delay)
                        continue
                # Non-retryable error — fail immediately
                break
                
        raise RuntimeError(f"Failed to generate instructions from LLM: {str(last_error)}")
