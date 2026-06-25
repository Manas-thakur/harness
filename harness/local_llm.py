#!/usr/bin/env python3
"""
Local LLM Provider with Ollama and GGUF support.
Auto-detects backends and provides unified interface.
"""

import asyncio
import os
import subprocess
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass


@dataclass
class ModelInfo:
    name: str
    backend: str  # 'ollama' or 'gguf'
    size_gb: float = 0.0
    context_window: int = 4096


class LocalLLMProvider:
    """Unified local LLM provider supporting Ollama and GGUF."""
    
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self.backend: Optional[str] = None
        self.model_info: Optional[ModelInfo] = None
        self._session = None
    
    async def initialize(self) -> bool:
        """Initialize the provider and detect backend."""
        # Try Ollama first
        if await self._check_ollama():
            self.backend = 'ollama'
            if self.model_path:
                self.model_info = ModelInfo(name=self.model_path, backend='ollama')
            else:
                # Default to llama3.1
                self.model_info = ModelInfo(name='llama3.1', backend='ollama')
            return True
        
        # Fall back to GGUF
        if self.model_path and Path(self.model_path).exists():
            self.backend = 'gguf'
            self.model_info = ModelInfo(name=self.model_path, backend='gguf')
            return True
        
        return False
    
    async def _check_ollama(self) -> bool:
        """Check if Ollama is running."""
        try:
            proc = await asyncio.create_subprocess_exec(
                'curl', '-s', 'http://localhost:11434/api/tags',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            if proc.returncode == 0:
                data = json.loads(stdout)
                return 'models' in data
        except Exception:
            pass
        return False
    
    async def list_models(self) -> List[ModelInfo]:
        """List available models."""
        models = []
        
        if self.backend == 'ollama':
            try:
                proc = await asyncio.create_subprocess_exec(
                    'curl', '-s', 'http://localhost:11434/api/tags',
                    stdout=asyncio.subprocess.PIPE
                )
                stdout, _ = await proc.communicate()
                data = json.loads(stdout)
                for m in data.get('models', []):
                    models.append(ModelInfo(
                        name=m['name'],
                        backend='ollama',
                        size_gb=m.get('size', 0) / (1024**3),
                        context_window=4096  # Default, can be improved
                    ))
            except Exception:
                pass
        
        return models
    
    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        stream: bool = False
    ):
        """Generate text from the model."""
        if self.backend == 'ollama':
            return await self._ollama_generate(prompt, system, max_tokens, temperature, stream)
        elif self.backend == 'gguf':
            return await self._gguf_generate(prompt, system, max_tokens, temperature, stream)
        else:
            raise RuntimeError("No backend initialized")
    
    async def _ollama_generate(
        self,
        prompt: str,
        system: Optional[str],
        max_tokens: int,
        temperature: float,
        stream: bool
    ):
        """Generate using Ollama API."""
        model_name = self.model_info.name if self.model_info else 'llama3.1'
        
        payload = {
            'model': model_name,
            'prompt': prompt,
            'stream': stream,
            'options': {
                'num_predict': max_tokens,
                'temperature': temperature
            }
        }
        
        if system:
            payload['system'] = system
        
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                'http://localhost:11434/api/generate',
                json=payload
            ) as resp:
                if stream:
                    async for line in resp.content:
                        if line.strip():
                            data = json.loads(line)
                            yield data.get('response', '')
                else:
                    data = await resp.json()
                    yield data.get('response', '')
    
    async def _gguf_generate(
        self,
        prompt: str,
        system: Optional[str],
        max_tokens: int,
        temperature: float,
        stream: bool
    ):
        """Generate using llama-cpp-python (GGUF)."""
        try:
            from llama_cpp import Llama
            
            llm = Llama(
                model_path=self.model_path,
                n_ctx=self.model_info.context_window if self.model_info else 4096,
                n_gpu_layers=-1  # Auto GPU offload
            )
            
            full_prompt = f"<|system|>\n{system or 'You are a helpful assistant.'}\n<|user|>\n{prompt}\n<|assistant|>\n"
            
            output = llm(
                full_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=stream
            )
            
            if stream:
                for chunk in output:
                    yield chunk['choices'][0]['text']
            else:
                yield output['choices'][0]['text']
                
        except ImportError:
            raise RuntimeError("llama-cpp-python not installed. Run: pip install llama-cpp-python")
    
    async def pull_model(self, model_name: str) -> bool:
        """Pull a model from Ollama."""
        if self.backend != 'ollama':
            return False
        
        try:
            proc = await asyncio.create_subprocess_exec(
                'ollama', 'pull', model_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            
            async for line in proc.stdout:
                print(f"Pulling {model_name}: {line.decode().strip()}")
            
            await proc.wait()
            return proc.returncode == 0
            
        except Exception as e:
            print(f"Error pulling model: {e}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """Check provider health."""
        status = {
            'backend': self.backend,
            'model': self.model_info.name if self.model_info else None,
            'healthy': False,
            'error': None
        }
        
        if self.backend == 'ollama':
            try:
                proc = await asyncio.create_subprocess_exec(
                    'curl', '-s', 'http://localhost:11434/api/tags',
                    stdout=asyncio.subprocess.PIPE
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
                if proc.returncode == 0:
                    status['healthy'] = True
            except Exception as e:
                status['error'] = str(e)
        
        elif self.backend == 'gguf':
            status['healthy'] = Path(self.model_path).exists()
            if not status['healthy']:
                status['error'] = f"Model file not found: {self.model_path}"
        
        return status
