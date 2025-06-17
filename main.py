import os
import uuid
import time
import json
import asyncio
import base64
import logging
from typing import List, Dict, Any, Union, Optional, Tuple
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError
import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(title="Gemini Backend for Vercel")

# Model cache for performance optimization
MODEL_CACHE = {}
API_KEY_CACHE = {}
RESPONSE_CACHE = {}

# Cache management with TTL
class ResponseCache:
    def __init__(self, ttl_seconds: int = 3600):
        self.cache = {}
        self.ttl = ttl_seconds
    
    def _make_key(self, messages, model, generation_config):
        """Create cache key from request parameters"""
        key_data = {
            'messages': str(messages),
            'model': model,
            'config': str(generation_config)
        }
        return hash(str(key_data))
    
    def get(self, messages, model, generation_config):
        """Get cached response if valid"""
        if not ENABLE_RESPONSE_CACHING:
            return None
            
        key = self._make_key(messages, model, generation_config)
        if key in self.cache:
            cached_item = self.cache[key]
            if time.time() - cached_item['timestamp'] < self.ttl:
                logger.info(f"Cache hit for key: {key}")
                return cached_item['response']
            else:
                # Expired, remove from cache
                del self.cache[key]
        return None
    
    def set(self, messages, model, generation_config, response):
        """Cache response with timestamp"""
        if not ENABLE_RESPONSE_CACHING:
            return
            
        key = self._make_key(messages, model, generation_config)
        self.cache[key] = {
            'response': response,
            'timestamp': time.time()
        }
        logger.info(f"Cached response for key: {key}")
        
        # Simple cache size management
        if len(self.cache) > 1000:  # Max 1000 cached responses
            # Remove oldest 100 entries
            oldest_keys = sorted(self.cache.keys(), 
                               key=lambda k: self.cache[k]['timestamp'])[:100]
            for old_key in oldest_keys:
                del self.cache[old_key]

# Initialize response cache
response_cache = ResponseCache(CACHE_TTL_SECONDS)

# API Keys - Orijinal hardcoded sistem korundu (PERFORMANS ETKİSİ YOK)
API_KEYS = [
"AIzaSyCT1PXjhup0VHx3Fz4AioHbVUHED0fVBP4",
    "AIzaSyArNqpA1EeeXBx-S3EVnP0tzao6r4BQnO0",
    "AIzaSyCXICPfRTnNAFwNQMmtBIb3Pi0pR4SydHg",
    "AIzaSyDiLvp7CU443luErAz3Ck0B8zFdm8UvNRs",
    "AIzaSyBzqJebfbVPcBXQy7r4Y5sVgC499uV85i0",
    "AIzaSyD6AFGKycSp1glkNEuARknMLvo93YbCqH8",
    "AIzaSyBTara5UhTbLR6qnaUI6nyV4wugycoABRM",
    "AIzaSyBI2Jc8mHJgjnXnx2udyibIZyNq8SGlLSY",
    "AIzaSyAcgdqbZsX9UOG4QieFSW7xCcwlHzDSURY",
    "AIzaSyAwOawlX-YI7_xvXY-A-3Ks3k9CxiTQfy4",
    "AIzaSyCJVUeJkqYeLNG6UsF06Gasn4mvMFfPhzw",
    "AIzaSyBFOK0YgaQOg5wilQul0P2LqHk1BgeYErw",
    "AIzaSyBQRsGHOhaiD2cNb5F68hI6BcZR7CXqmwc",
    "AIzaSyCIC16VVTlFGbiQtq7RlstTTqPYizTB7yQ",
    "AIzaSyCIlfHXQ9vannx6G9Pae0rKwWJpdstcZIM",
    "AIzaSyAUIR9gx08SNgeHq8zKAa9wyFtFu00reTM",
    "AIzaSyAST1jah1vAcnLfmofR4DDw0rjYkJXJoWg",
    "AIzaSyAV8OU1_ANXTIvkRooikeNrI1EMR3IbTyQ",
    "AIzaSyDjv4WUz2s6pls0LzfUdt3F_igv2ZPUKVg",
    "AIzaSyDSiZKmUc8Etkr4pyPxXBdVHzQSxL9GNwg",
    "AIzaSyAhOMabpXZnFuzZU1QIYA67Xgo99HYKJ_U",
    "AIzaSyBRZhLcs6mPpkxIJhK8tRSjh1K8FBkL9Iw",
"AIzaSyBYE0Kkx7TZaBTAIuNbe1IifKK4M-sqy_w",
"AIzaSyDs6coRymAgQuDOYEymjYpZehZcPexLZMs",
"AIzaSyBkrBIU3rMMMvBfyrQ7COacDZPEdj94FD4",
"AIzaSyAYrB5t4cRfLYjH_BGAC9KmoVsBmNGZkVs",
    "AIzaSyAgLy9ZXGFHZ93nzLUExFHbn7-3FNGuEXA",
    "AIzaSyBOX_c3fOAOKudfVvoLVETV8TNGi1vp4go",
    "AIzaSyD_DB9NYaNb4cfSXRQmC7EI0hxVLIneJ3g",
    "AIzaSyAfnjwTDk1Md6JswVG12GRIqIa7RWi8nr4",
    "AIzaSyDMypd1IWza4MfOfZEdaENCFddeIdBtKHQ",
    "AIzaSyDCMpkrRw2ruX1NwJbm6zQKTzgNxAnUNhQ",
]

# Performance configuration - Bu ayarlar gerçek performans etkisi yapar
MODEL_CACHE_SIZE = 100
API_KEY_CACHE_SIZE = 50  
ENABLE_RESPONSE_CACHING = True  # ⚡ BÜYÜK PERFORMANS ETKİSİ
CACHE_TTL_SECONDS = 3600

'''API KEYS GMAIL
omer1476hotmail@gmail.com
ebuubeydeelkassam@gmail.com
endustriyelyildiz@gmail.com
zixzox1481@gmail.com
wheelweightsmachine@gmail.com
myildiz1476@gmail.com
zirzox1@gmail.com
zirzox2@gmail.com
zirzox1476@gmail.com
zirzox4@gmail.com
zirzox1482@gmail.com
m08015846@gmail.com
m46473401@gmail.com 
dasd2323r23r3@gmail.com
dasasdafawefa@gmail.com
defmehme254@gmail.com
1476ggssgg1476@gmail.com
e00286251@gmail.com
wqerqr6@gmail.com
????????
hamza
opkdaopskdopksad@gmail.com
dqerf3242rdfsdf@gmail.com
fasefasdasd0@gmail.com
dasdsads143@gmail.com
sadasf34235sdaf@gmail.com
hafize1476@gmail.com
adfersdaasdasd@gmail.com
dwqqdsadasdw@gmail.com
swaqdawdasfdsaf@gmail.com
hafize.yildiz.448@gmail.com
'''

# Pydantic Models
class ImageUrl(BaseModel):
    url: str

class ContentItem(BaseModel):
    type: str
    text: Optional[str] = None
    image_url: Optional[ImageUrl] = None

class Message(BaseModel):
    role: str
    content: Union[str, List[ContentItem]]

class ChatRequest(BaseModel):
    model: str
    messages: List[Message]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: bool = False

def process_content(content):
    """Convert OpenAI format to Gemini format"""
    if isinstance(content, str):
        return [{"text": content}]
    
    parts = []
    for item in content:
        if item.type == "text" and item.text:
            parts.append({"text": item.text})
        elif item.type == "image_url" and item.image_url:
            try:
                # Handle base64 images
                if item.image_url.url.startswith("data:"):
                    header, base64_data = item.image_url.url.split(",", 1)
                    mime_type = header.split(";")[0].split(":")[1]
                    parts.append({
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": base64_data
                        }
                    })
            except:
                parts.append({"text": "[Image processing error]"})
    
    return parts or [{"text": ""}]

def convert_messages(messages):
    """Convert OpenAI messages to Gemini format"""
    return [
        {
            "role": "user" if msg.role == "user" else "model",
            "parts": process_content(msg.content)
        }
        for msg in messages
    ]

async def stream_openai_response(gemini_stream: Any, model: str):
    """Stream Gemini response in OpenAI-compatible chunked format."""
    chunk_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())

    # Initial chunk - role başlangıcı
    initial_chunk = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{
            "index": 0,
            "delta": {"role": "assistant"},
            "finish_reason": None
        }]
    }
    try:
        yield f"data: {json.dumps(initial_chunk)}\n\n"
    except BrokenPipeError:
        logger.warning("Client disconnected during initial chunk (BrokenPipeError).")
        return

    try:
        for response_chunk in gemini_stream:
            content_parts = []
            finish_reason = None

            if response_chunk.candidates:
                for candidate in response_chunk.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if hasattr(part, 'text'):
                                content_parts.append(part.text)
                    
                    # Check for finish_reason from Gemini's response_chunk
                    if hasattr(candidate, 'finish_reason') and candidate.finish_reason is not None:
                        # Map Gemini's FinishReason enum to OpenAI's string format
                        # genai.types.protos.FinishReason.STOP (1) -> "stop"
                        # genai.types.protos.FinishReason.MAX_TOKENS (2) -> "length"
                        if candidate.finish_reason == 1: # STOP
                            finish_reason = "stop"
                        elif candidate.finish_reason == 2: # MAX_TOKENS
                            finish_reason = "length"
                        # Add other mappings as needed for other finish reasons

            content = "".join(content_parts)

            # Send a chunk if there's content or a finish reason
            if content or finish_reason:
                content_chunk = {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": content} if content else {},
                        "finish_reason": finish_reason
                    }]
                }
                yield f"data: {json.dumps(content_chunk)}\n\n"

    except Exception as e:
        logger.error("Streaming error: %s", str(e))
        error_chunk = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {"content": f"Streaming error: {str(e)}"},
                "finish_reason": "error"
            }]
        }
        try:
            yield f"data: {json.dumps(error_chunk)}\n\n"
            yield "data: [DONE]\n\n"
        except BrokenPipeError:
            logger.warning("Client disconnected during error handling (BrokenPipeError).")
        return

    # Ensure a final stop chunk is sent if not already handled by a finish_reason in the stream
    # This handles cases where the stream ends without an explicit finish_reason in the last chunk.
    final_chunk = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{
            "index": 0,
            "delta": {}, # Empty delta
            "finish_reason": "stop"
        }]
    }
    try:
        yield f"data: {json.dumps(final_chunk)}\n\n"
    except BrokenPipeError:
        logger.warning("Client disconnected during final chunk (BrokenPipeError).")
        return


def get_cached_model(api_key: str, model: str) -> Any:
    """Get cached model instance or create new one"""
    cache_key = f"{api_key[:10]}_{model}"
    
    if cache_key not in MODEL_CACHE:
        # Configure API key only if not already configured for this key
        if api_key not in API_KEY_CACHE:
            genai.configure(api_key=api_key)
            API_KEY_CACHE[api_key] = True
            
        MODEL_CACHE[cache_key] = genai.GenerativeModel(model)
        logger.info(f"Created new model instance for cache key: {cache_key[:20]}...")
    
    return MODEL_CACHE[cache_key]

async def make_gemini_request(api_key: str, model: str, messages: list, generation_config: dict, stream: bool = False) -> Any:
    """Make a request to the Gemini API with cached model instance."""
    gemini_model = get_cached_model(api_key, model)

    try:
        if stream:
            # For streaming, generate_content returns an iterable.
            # The library handles the streaming nature internally.
            return gemini_model.generate_content(
                contents=messages,
                generation_config=generation_config,
                stream=True
            )
        else:
            # For non-streaming, use the async version
            return await gemini_model.generate_content_async(
                contents=messages,
                generation_config=generation_config
            )
    except Exception as e:
        logger.error("Error making Gemini request: %s", str(e))
        raise

@app.post("/v1/chat/completions")
async def chat_completions(chat_request: ChatRequest, request: Request):
    # Unique version identifier for debugging
    logger.info("Backend main.py version: 20250604_01")
    try:
        # Get the backend index from the custom header
        backend_index_str = request.headers.get("X-Backend-Index")
        if backend_index_str is None:
            logger.warning("X-Backend-Index header not found. Using default key (index 0).")
            backend_index = 0
        else:
            try:
                backend_index = int(backend_index_str)
                if not (0 <= backend_index < len(API_KEYS)):
                    logger.warning(f"Invalid X-Backend-Index: {backend_index}. Using default key (index 0).")
                    backend_index = 0
            except ValueError:
                logger.warning(f"Invalid X-Backend-Index format: {backend_index_str}. Using default key (index 0).")
                backend_index = 0

        api_key = API_KEYS[backend_index]
        logger.info(f"Using API Key from index: {backend_index}")

        # Convert messages
        gemini_messages = convert_messages(chat_request.messages)
        generation_config = {}
        
        # Temperature'ı sadece istemci gönderdiyse ekle
        if chat_request.temperature is not None:
            generation_config["temperature"] = chat_request.temperature
        
        # Max Output Tokens'ı sadece pozitif bir değerse ekle
        if chat_request.max_tokens is not None and chat_request.max_tokens != -1:
            generation_config["max_output_tokens"] = chat_request.max_tokens
        
        # Check cache for non-streaming requests
        if not chat_request.stream:
            cached_response = response_cache.get(gemini_messages, chat_request.model, generation_config)
            if cached_response:
                logger.info("Returning cached response")
                # Add cache hit header
                cached_response["cached"] = True
                return cached_response
        
        # Gemini API çağrısı
        response = await make_gemini_request(
            api_key,
            chat_request.model,
            gemini_messages,
            generation_config,
            stream=chat_request.stream # Pass stream parameter
        )
        
        if chat_request.stream:
            return StreamingResponse(
                stream_openai_response(response, chat_request.model),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                }
            )

        # Regular response (non-streaming)
        text = ""
        if response.candidates and len(response.candidates) > 0:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts:
                text = "".join(part.text for part in candidate.content.parts if part.text)

        response_data = {
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": chat_request.model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": len(str(chat_request.messages)), # This will be inaccurate for genai, but keeping for now
                "completion_tokens": len(text),
                "total_tokens": len(str(chat_request.messages)) + len(text)
            }
        }
        
        # Cache the response for future use
        response_cache.set(gemini_messages, chat_request.model, generation_config, response_data)
        
        return response_data
        
    except HTTPException:
        raise
    except GoogleAPIError as e:
        logger.error("Gemini API error: %s", str(e))
        if "Quota exceeded" in str(e) or "Resource has been exhausted" in str(e):
            # For now, just raise 429. No retry logic from the example yet.
            raise HTTPException(status_code=429, detail="Rate limit exceeded for Gemini API")
        raise HTTPException(status_code=500, detail=f"Gemini API error: {str(e)}")
    except Exception as e:
        logger.error("Internal error: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": int(time.time()),
        "total_api_keys": len(API_KEYS),
        "cached_models": len(MODEL_CACHE),
        "cached_api_keys": len(API_KEY_CACHE),
        "cached_responses": len(response_cache.cache),
        "caching_enabled": ENABLE_RESPONSE_CACHING,
        "cache_ttl": CACHE_TTL_SECONDS,
        "version": "2.0.0-optimized"
    }

@app.get("/metrics")
async def metrics():
    """Detailed metrics endpoint for monitoring"""
    cache_stats = {
        "total_cached_responses": len(response_cache.cache),
        "cache_hits": sum(1 for item in response_cache.cache.values() 
                         if time.time() - item['timestamp'] < CACHE_TTL_SECONDS),
        "expired_entries": sum(1 for item in response_cache.cache.values() 
                              if time.time() - item['timestamp'] >= CACHE_TTL_SECONDS)
    }
    
    return {
        "timestamp": int(time.time()),
        "cache": cache_stats,
        "models": {
            "total_cached": len(MODEL_CACHE),
            "cache_keys": list(MODEL_CACHE.keys()) if len(MODEL_CACHE) < 10 else f"{len(MODEL_CACHE)} cached models"
        },
        "api_keys": {
            "total_available": len(API_KEYS),
            "configured_keys": len(API_KEY_CACHE)
        },
        "configuration": {
            "caching_enabled": ENABLE_RESPONSE_CACHING,
            "cache_ttl": CACHE_TTL_SECONDS,
            "model_cache_size": MODEL_CACHE_SIZE,
            "api_key_cache_size": API_KEY_CACHE_SIZE
        }
    }

@app.post("/admin/clear-cache")
async def clear_cache():
    """Clear all caches - admin endpoint"""
    MODEL_CACHE.clear()
    API_KEY_CACHE.clear()
    response_cache.cache.clear()
    
    return {
        "status": "success",
        "message": "All caches cleared",
        "timestamp": int(time.time())
    }

@app.get("/v1/models")
async def list_models():
    """List available models endpoint for OpenAI compatibility"""
    return {
        "object": "list",
        "data": [
            {
                "id": "gemini-2.5-flash-preview-05-20",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "google"
            },
            {
                "id": "gemini-1.5-pro",
                "object": "model", 
                "created": int(time.time()),
                "owned_by": "google"
            },
            {
                "id": "gemini-1.5-flash",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "google"
            }
        ]
    }

@app.get("/")
async def root():
    return {
        "message": "Gemini Proxy API",
        "version": "1.0.0",
        "endpoints": ["/v1/chat/completions", "/v1/models", "/health"]
    }

# CORS Middleware
@app.middleware("http")
async def cors_handler(request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
    response.headers["Access-Control-Max-Age"] = "86400"
    
    # OPTIONS request handling
    if request.method == "OPTIONS":
        response.status_code = 200
    
    return response
