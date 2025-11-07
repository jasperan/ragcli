"""Embedding and LLM generation via Ollama API for ragcli."""

import requests
import time
import json
from typing import List, Dict, Any, Generator, Optional
from ragcli.config.config_manager import load_config

def generate_embedding(text: str, model: str, config: dict) -> List[float]:
    """Generate embedding for text using Ollama API."""
    endpoint = config['ollama']['endpoint']
    timeout = config['ollama']['timeout']
    
    payload = {
        "model": model,
        "prompt": text
    }
    
    for attempt in range(3):  # 3 retries
        try:
            response = requests.post(
                f"{endpoint}/api/embeddings",
                json=payload,
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()["embedding"]
        except requests.RequestException as e:
            if attempt == 2:
                raise Exception(f"Failed to generate embedding after 3 attempts: {e}")
            wait_time = 2 ** attempt  # Exponential backoff: 2, 4s
            time.sleep(wait_time)
    
    raise Exception("Unexpected error in generate_embedding")

def generate_response(
    messages: List[Dict[str, str]],
    model: str,
    config: dict,
    stream: bool = False
) -> Optional[Generator[str, None, None]]:
    """Generate response using Ollama chat API, with streaming support."""
    endpoint = config['ollama']['endpoint']
    timeout = config['ollama']['timeout']
    
    payload = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "temperature": 0.7,  # Default
    }
    
    for attempt in range(3):
        try:
            response = requests.post(
                f"{endpoint}/api/chat",
                json=payload,
                timeout=timeout,
                stream=stream
            )
            response.raise_for_status()
            
            if stream:
                def generate_tokens():
                    for line in response.iter_lines():
                        if line:
                            data = json.loads(line.decode('utf-8').replace("data: ", ""))
                            if "choices" in data and "delta" in data["choices"][0]:
                                yield data["choices"][0]["delta"].get("content", "")
                return generate_tokens()
            else:
                return response.json()["message"]["content"]
        except requests.RequestException as e:
            if attempt == 2:
                raise Exception(f"Failed to generate response after 3 attempts: {e}")
            wait_time = 2 ** attempt
            time.sleep(wait_time)
    
    raise Exception("Unexpected error in generate_response")

# TODO: Add token counting, OpenAI-compatible endpoint support, more error handling
