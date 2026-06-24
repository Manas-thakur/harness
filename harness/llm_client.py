"""
LLM Client for Local Ollama Instance
Handles communication with local Ollama server and JSON repair for unreliable model outputs.
"""

import re
import json
import ollama
from typing import Dict, List, Any, Optional


def repair_and_extract_json(text: str) -> dict:
    """
    Repair and extract JSON from potentially malformed LLM output.
    Local 7B models often output markdown around JSON or miss closing brackets.
    
    Args:
        text: Raw text output from LLM
        
    Returns:
        Parsed dictionary
        
    Raises:
        ValueError: If no valid JSON can be extracted
    """
    # 1. Find the first { 
    start = text.find('{')
    if start == -1:
        raise ValueError("No JSON object found in text")
    
    # Try to find matching } by counting braces
    open_count = 0
    end = -1
    for i, char in enumerate(text[start:], start):
        if char == '{':
            open_count += 1
        elif char == '}':
            open_count -= 1
            if open_count == 0:
                end = i
                break
    
    # If no matching brace found, try rfind as fallback
    if end == -1:
        end = text.rfind('}')
        if end == -1:
            # No closing brace at all - add one
            json_str = text[start:] + '}'
        else:
            json_str = text[start:end+1]
    else:
        json_str = text[start:end+1]
    
    # 2. Attempt to parse directly
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass
    
    # 3. Basic repair: remove trailing commas before } or ]
    json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass
    
    # 4. Remove markdown code blocks if present
    json_str = re.sub(r'```json\s*', '', json_str)
    json_str = re.sub(r'```\s*', '', json_str)
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass
    
    # 5. Try to fix common issues - Add missing closing braces
    open_braces = json_str.count('{')
    close_braces = json_str.count('}')
    if open_braces > close_braces:
        json_str += '}' * (open_braces - close_braces)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
    
    # 6. Try removing any remaining whitespace issues
    json_str = json_str.strip()
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass
    
    raise ValueError(f"Failed to repair JSON: {text[:200]}")


class LocalLLMClient:
    """
    Client for interacting with local Ollama LLM instance.
    Optimized for RTX 4060 8GB VRAM with Qwen2.5-7B.
    """
    
    def __init__(
        self, 
        model: str = "qwen2.5:7b",
        host: str = "http://localhost:11434",
        timeout: int = 120
    ):
        """
        Initialize the LLM client.
        
        Args:
            model: Model name to use (default: qwen2.5:7b)
            host: Ollama server host URL
            timeout: Request timeout in seconds
        """
        self.model = model
        self.host = host
        self.timeout = timeout
        
        # Configure ollama client
        ollama._client._host = host
    
    def generate(
        self, 
        messages: List[Dict[str, str]], 
        temperature: float = 0.7,
        stream: bool = False
    ) -> str:
        """
        Generate text response from LLM.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0-1.0)
            stream: Whether to stream response
            
        Returns:
            Generated text content
        """
        try:
            response = ollama.chat(
                model=self.model,
                messages=messages,
                options={
                    "temperature": temperature,
                    "num_predict": 4096  # Limit max tokens
                },
                stream=stream
            )
            
            if stream:
                content = ""
                for chunk in response:
                    if 'message' in chunk and 'content' in chunk['message']:
                        content += chunk['message']['content']
                return content
            else:
                return response['message']['content']
                
        except ollama.ResponseError as e:
            raise RuntimeError(f"LLM request failed: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error during generation: {str(e)}")
    
    def generate_structured(
        self, 
        messages: List[Dict[str, str]], 
        temperature: float = 0.3
    ) -> Dict[str, Any]:
        """
        Generate structured JSON output from LLM.
        Uses JSON repair to handle malformed outputs.
        
        Args:
            messages: List of message dicts
            temperature: Lower temperature for more deterministic output
            
        Returns:
            Parsed dictionary from LLM response
        """
        response_text = self.generate(messages, temperature=temperature)
        return repair_and_extract_json(response_text)
    
    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        Simple estimation: 1 token ≈ 4 characters for English text.
        
        Args:
            text: Input text
            
        Returns:
            Estimated token count
        """
        return len(text) // 4
    
    def is_available(self) -> bool:
        """
        Check if Ollama server is available and model is loaded.
        
        Returns:
            True if server is reachable and model exists
        """
        try:
            # Try to list models
            models = ollama.list()
            model_names = [m.get('name', '') for m in models.get('models', [])]
            return any(self.model in name for name in model_names)
        except Exception:
            return False
