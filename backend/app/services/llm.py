"""LLM service — Google Gemini via LangChain ChatGoogleGenerativeAI.

All agents use this service. Provides both a high-level LangChain
integration (with tool binding support) and a simple call_llm() helper.
"""

from collections.abc import AsyncIterator

from app.config import get_settings

MODEL_ROUTES = {
    "strategist": "gemini-2.0-flash",
    "copywriter": "gemini-2.0-flash",
    "visual_director": "gemini-2.0-flash",
    "designer": "gemini-2.0-flash",
    "quality_check": "gemini-2.0-flash",
    "token_generator": "gemini-2.5-flash",
}


def get_llm(agent_role: str = "strategist", temperature: float = 0.7, max_tokens: int | None = None):
    """Get a LangChain ChatGoogleGenerativeAI instance for the given role.

    Supports tool binding via .bind_tools() on the returned instance.
    Uses Gemini 2.0 Flash for most agents (free tier).
    """
    from langchain_google_genai import ChatGoogleGenerativeAI

    settings = get_settings()
    model = MODEL_ROUTES.get(agent_role, "gemini-2.0-flash")
    api_key = settings.gemini_api_key or None

    return ChatGoogleGenerativeAI(
        model=model,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
    )


async def call_llm(
    agent_role: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 2000,
) -> str:
    """Simple helper — calls LLM with system + user prompt and returns text.

    Uses LangChain's ChatGoogleGenerativeAI under the hood.
    Falls back to OpenRouter if Gemini fails and a key is configured.
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = get_llm(agent_role=agent_role, temperature=temperature, max_tokens=max_tokens)

    try:
        response = await llm.ainvoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
        return response.content if isinstance(response.content, str) else str(response.content)
    except Exception as gemini_error:
        settings = get_settings()
        if settings.openrouter_api_key:
            return await _call_openrouter(
                api_key=settings.openrouter_api_key,
                model=MODEL_ROUTES.get(agent_role, "gemini-2.0-flash"),
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        raise gemini_error


async def call_llm_stream(
    agent_role: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 2000,
) -> AsyncIterator[str]:
    """Stream response from LLM. Yields text chunks as they arrive."""
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = get_llm(agent_role=agent_role, temperature=temperature, max_tokens=max_tokens)

    try:
        async for chunk in llm.astream([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]):
            if content := chunk.content:
                yield content if isinstance(content, str) else str(content)
    except Exception as gemini_error:
        settings = get_settings()
        if settings.openrouter_api_key:
            async for chunk in _call_openrouter_stream(
                api_key=settings.openrouter_api_key,
                model=MODEL_ROUTES.get(agent_role, "gemini-2.0-flash"),
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                yield chunk
        else:
            raise gemini_error


async def _call_openrouter(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
) -> str:
    import openai

    client = openai.AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


async def _call_openrouter_stream(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
) -> AsyncIterator[str]:
    import openai

    client = openai.AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    stream = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
