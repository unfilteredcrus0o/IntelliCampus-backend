
import os
import time
import json
import logging
import asyncio
from typing import Optional, List
from concurrent.futures import ThreadPoolExecutor

import requests
import httpx
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


class LLMClientError(Exception):
    pass

def create_session_with_retries():
    """Create requests session with retry configuration"""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

# Global session instance
session = create_session_with_retries()

def call_llm(prompt: str, temperature: float = 0.7, max_tokens: Optional[int] = None) -> str:
    if LLM_PROVIDER == "groq":
        return call_groq_enhanced(prompt, temperature, max_tokens)
    else:
        raise ValueError(f"Unsupported LLM provider: {LLM_PROVIDER}")

def call_llm_with_retry(prompt: str, max_retries: int = 3, temperature: float = 0.7) -> str:

    last_error = None
    
    for attempt in range(max_retries):
        try:
            return call_llm(prompt, temperature)
        except Exception as e:
            last_error = e
            if attempt == max_retries - 1:
                break
            
            wait_time = (2 ** attempt) + (attempt * 0.1)
            logger.warning(f"LLM retry {attempt + 1}/{max_retries} in {wait_time:.1f}s")
            time.sleep(wait_time)
    
    logger.error(f"LLM failed after {max_retries} attempts: {type(last_error).__name__}")
    raise LLMClientError(f"LLM call failed: {last_error}")

def call_groq_enhanced(prompt: str, temperature: float = 0.7, max_tokens: Optional[int] = None) -> str:

    if not GROQ_API_KEY:
        raise LLMClientError("GROQ_API_KEY environment variable not set")
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "LearningPlatform/1.0"
    }
    
    data = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system", 
                "content": "You are an expert educator and knowledge synthesizer. Provide accurate, comprehensive, and well-structured responses that help learners understand complex topics."
            },
            {
                "role": "user", 
                "content": prompt
            }
        ],
        "temperature": temperature,
        "top_p": 0.9,
        "frequency_penalty": 0.1,
        "presence_penalty": 0.1,
        "stream": False
    }
    
    if max_tokens:
        data["max_tokens"] = max_tokens
    
    try:
        response = session.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 401:
            raise LLMClientError("Invalid API key")
        elif response.status_code == 429:
            retry_after = response.headers.get('Retry-After', '60')
            raise LLMClientError(f"Rate limit exceeded. Retry after {retry_after} seconds")
        elif response.status_code == 503:
            raise LLMClientError("Service temporarily unavailable")
        elif response.status_code != 200:
            error_detail = response.text
            logger.error(f"Groq API {response.status_code}")
            raise LLMClientError(f"API request failed with status {response.status_code}")
        
        response_data = response.json()
        
        if "choices" not in response_data or not response_data["choices"]:
            raise LLMClientError("Invalid response structure from API")
        
        content = response_data["choices"][0]["message"]["content"]
        

        
        return content.strip()
        
    except requests.exceptions.Timeout:
        raise LLMClientError("Request timeout - API took too long to respond")
    except requests.exceptions.ConnectionError:
        raise LLMClientError("Connection error - unable to reach API")
    except requests.exceptions.RequestException as e:
        raise LLMClientError(f"Request failed: {str(e)}")
    except json.JSONDecodeError:
        raise LLMClientError("Invalid JSON response from API")
    except KeyError as e:
        raise LLMClientError(f"Missing expected field in API response: {e}")

def validate_json_response(response: str) -> bool:

    try:
        json.loads(response.strip())
        return True
    except json.JSONDecodeError:
        return False

def call_llm_with_json_validation(prompt: str, max_retries: int = 3) -> str:

    for attempt in range(max_retries):
        try:
            response = call_llm(f"{prompt}\n\nIMPORTANT: Return ONLY valid JSON, no additional text.")
            
            if validate_json_response(response):
                return response
            else:

                if attempt == max_retries - 1:
                    raise LLMClientError("Failed to get valid JSON after all attempts")
                    
        except Exception as e:
            if attempt == max_retries - 1:
                raise e

    
    raise LLMClientError("All attempts failed")

# Async LLM functions for better performance
async def call_llm_async(prompt: str, temperature: float = 0.7, max_tokens: Optional[int] = None) -> str:
    """Async version of call_llm for better performance"""
    if LLM_PROVIDER == "groq":
        return await call_groq_async(prompt, temperature, max_tokens)
    else:
        raise ValueError(f"Unsupported LLM provider: {LLM_PROVIDER}")

async def call_groq_async(prompt: str, temperature: float = 0.7, max_tokens: Optional[int] = None) -> str:
    """Async Groq API call with better performance"""
    if not GROQ_API_KEY:
        raise LLMClientError("GROQ_API_KEY environment variable not set")
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "LearningPlatform/1.0"
    }
    
    data = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system", 
                "content": "You are an expert educator. Provide accurate, concise responses in the requested format."
            },
            {
                "role": "user", 
                "content": prompt
            }
        ],
        "temperature": temperature,
        "top_p": 0.9,
        "stream": False
    }
    
    if max_tokens:
        data["max_tokens"] = max_tokens
    
    try:
        timeout = httpx.Timeout(15.0)  # Reduced timeout
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=data
            )
                
            if response.status_code == 401:
                raise LLMClientError("Invalid API key")
            elif response.status_code == 429:
                retry_after = response.headers.get('Retry-After', '60')
                raise LLMClientError(f"Rate limit exceeded. Retry after {retry_after} seconds")
            elif response.status_code == 503:
                raise LLMClientError("Service temporarily unavailable")
            elif response.status_code != 200:
                error_text = response.text
                logger.error(f"Groq API {response.status_code}: {error_text}")
                raise LLMClientError(f"API request failed with status {response.status_code}")
            
            response_data = response.json()
                
            if "choices" not in response_data or not response_data["choices"]:
                raise LLMClientError("Invalid response structure from API")
            
            content = response_data["choices"][0]["message"]["content"]
            return content.strip()
        
    except httpx.TimeoutException:
        raise LLMClientError("Request timeout - API took too long to respond")
    except httpx.RequestError as e:
        raise LLMClientError(f"Request failed: {str(e)}")
    except json.JSONDecodeError:
        raise LLMClientError("Invalid JSON response from API")
    except KeyError as e:
        raise LLMClientError(f"Missing expected field in API response: {e}")

async def batch_llm_calls(prompts: List[str], temperature: float = 0.7, max_tokens: Optional[int] = None) -> List[str]:
    """Process multiple LLM calls concurrently for better performance"""
    tasks = [call_llm_async(prompt, temperature, max_tokens) for prompt in prompts]
    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions in results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Batch call {i} failed: {result}")
                processed_results.append(f"Error: {str(result)}")
            else:
                processed_results.append(result)
        
        return processed_results
    except Exception as e:
        logger.error(f"Batch processing failed: {e}")
        raise LLMClientError(f"Batch processing failed: {e}")

def call_llm_batch_sync(prompts: List[str], temperature: float = 0.7, max_tokens: Optional[int] = None) -> List[str]:
    """Synchronous wrapper for batch async calls"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(batch_llm_calls(prompts, temperature, max_tokens))

# Optimized prompts for faster processing
def create_optimized_roadmap_prompt(topic: str, duration: str, skill_level: str) -> str:
    """Create a more concise prompt for faster processing"""
    return f"""Create a {skill_level} learning roadmap for "{topic}" over {duration}.

Return JSON with 3-4 milestones, each with 2-3 specific topics:
{{
  "milestones": [
    {{
      "name": "milestone name",
      "description": "brief description", 
      "topics": ["topic1", "topic2"],
      "estimated_duration": "time estimate"
    }}
  ]
}}

Focus on practical, actionable content. Return ONLY valid JSON."""

def create_fast_explanation_prompt(topic_name: str) -> str:
    """Create a concise prompt for topic explanations"""
    return f"""Explain "{topic_name}" for learning.

Return JSON:
{{
  "content": "# {topic_name}\\n\\n## Overview\\n[brief explanation]\\n\\n## Key Concepts\\n[main points]\\n\\n## Practice\\n[how to apply]",
  "difficulty_level": "beginner|intermediate|advanced",
  "estimated_time": "X minutes"
}}

Keep it concise but comprehensive. Return ONLY valid JSON."""