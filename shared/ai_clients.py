"""
Shared AI service clients (OpenAI, Gemini).
"""
from typing import List, Optional

from django.conf import settings


class OpenAIClient:
    """OpenAI API client for embeddings and completions."""

    def __init__(self):
        self._client = None

    @property
    def client(self):
        """Lazy load OpenAI client."""
        if self._client is None:
            import openai
            self._client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        return self._client

    def create_embedding(self, text: str) -> List[float]:
        """Create embedding vector synchronously."""
        import logging
        logger = logging.getLogger(__name__)
        
        # API 키 검증
        if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == 'your-openai-api-key':
            error_msg = "OpenAI API 키가 설정되지 않았습니다. .env 파일에 OPENAI_API_KEY를 설정해주세요."
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        try:
            response = self.client.embeddings.create(
                model=settings.EMBEDDING_MODEL,
                input=text,
            )
            return response.data[0].embedding
        except Exception as e:
            error_msg = f"OpenAI Embedding API 호출 실패: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e

    async def create_embedding_async(self, text: str) -> List[float]:
        """Create embedding vector asynchronously."""
        import openai
        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input=text,
        )
        return response.data[0].embedding

    def create_chat_completion(
        self,
        messages: List[dict],
        model: str = "gpt-4",
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        """Create a chat completion."""
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content


class GeminiClient:
    """Google Gemini API client."""

    def __init__(self):
        self._client = None

    @property
    def client(self):
        """Lazy load Gemini client."""
        if self._client is None:
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)

            self._client = genai.GenerativeModel('gemini-2.0-flash')
        return self._client

    def generate_content(self, prompt: str) -> str:
        """Generate content using Gemini."""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            response = self.client.generate_content(prompt)
            # response.text가 None일 수 있으므로 안전하게 처리
            if response and hasattr(response, 'text') and response.text:
                return response.text
            elif response and hasattr(response, 'text'):
                # text가 None인 경우
                error_msg = "Gemini API가 None 응답을 반환했습니다."
                logger.error(error_msg)
                raise ValueError(error_msg)
            else:
                # response 자체가 None이거나 예상과 다른 형식
                error_msg = f"Gemini API가 예상하지 못한 응답을 반환했습니다: {type(response)}"
                logger.error(error_msg)
                raise ValueError(error_msg)
        except Exception as e:
            logger.error(f"Gemini API 호출 실패: {str(e)}")
            raise

    def generate_with_context(
        self,
        prompt: str,
        context: str = "",
        temperature: float = 0.7,
    ) -> str:
        """Generate content with context."""
        full_prompt = f"{context}\n\n{prompt}" if context else prompt
        return self.generate_content(full_prompt)


# Singleton instances
_openai_client: Optional[OpenAIClient] = None
_gemini_client: Optional[GeminiClient] = None


def get_openai_client() -> OpenAIClient:
    """Get OpenAI client singleton."""
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAIClient()
    return _openai_client


def get_gemini_client() -> GeminiClient:
    """Get Gemini client singleton."""
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = GeminiClient()
    return _gemini_client
