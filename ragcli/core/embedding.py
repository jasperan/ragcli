"""Embedding and LLM generation via Ollama API for ragcli."""

import requests
import json
from typing import List, Dict, Any, Generator, Optional
from ragcli.config.config_manager import load_config
from ..utils.helpers import retry_with_backoff
from ..utils.logger import get_logger

logger = get_logger(__name__)

def generate_embedding(text: str, model: str, config: dict) -> List[float]:
    """Generate embedding for text using Ollama API with retry logic."""
    endpoint = config['ollama']['endpoint']
    timeout = config['ollama']['timeout']

    def _api_call():
        payload = {
            "model": model,
            "prompt": text
        }
        response = requests.post(
            f"{endpoint}/api/embeddings",
            json=payload,
            timeout=timeout
        )
        response.raise_for_status()
        return response.json()["embedding"]

    try:
        return retry_with_backoff(_api_call, max_retries=3, base_delay=1.0, max_delay=10.0)
    except Exception as e:
        logger.error(f"Failed to generate embedding for model {model}", exc_info=True)
        raise Exception(f"Embedding generation failed: {e}")

def generate_response(
    messages: List[Dict[str, str]],
    model: str,
    config: dict,
    stream: bool = False
) -> Optional[Generator[str, None, None]]:
    """Generate response using Ollama chat API with retry logic."""
    endpoint = config['ollama']['endpoint']
    timeout = config['ollama']['timeout']

    def _api_call():
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "temperature": 0.7,  # Default
        }
        response = requests.post(
            f"{endpoint}/api/chat",
            json=payload,
            timeout=timeout,
            stream=stream
        )
        response.raise_for_status()

        if stream:
            # For streaming, we need to handle it differently
            content = ""
            for line in response.iter_lines():
                if line:
                    data = json.loads(line.decode('utf-8').replace("data: ", ""))
                    if "choices" in data and "delta" in data["choices"][0]:
                        token = data["choices"][0]["delta"].get("content", "")
                        content += token
            return content
        else:
            return response.json()["message"]["content"]

    try:
        result = retry_with_backoff(_api_call, max_retries=3, base_delay=1.0, max_delay=10.0)
        if stream:
            # Convert back to generator for compatibility
            def generate_tokens():
                # Since we collected all content, yield it as one piece
                # TODO: Implement proper streaming with retries
                yield result
            return generate_tokens()
        else:
            return result
    except Exception as e:
        logger.error(f"Failed to generate response for model {model}", exc_info=True)
        raise Exception(f"Response generation failed: {e}")

# TODO: Add token counting, OpenAI-compatible endpoint support, more error handling
