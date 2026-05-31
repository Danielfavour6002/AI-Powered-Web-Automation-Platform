import json
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
            "gemini": "gemini/gemini-1.5-pro-latest",
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
            # Clean markdown formatting if present
            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]
                
            if content.endswith("```"):
                content = content[:-3]
                
            instructions = json.loads(content.strip())
            if not isinstance(instructions, list):
                raise ValueError("LLM did not return a list")
                
            return instructions
            
        except Exception as e:
            raise RuntimeError(f"Failed to generate instructions from LLM: {str(e)}")
