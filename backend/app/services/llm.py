"""LLM service — Google Gemini free tier via AI Studio.

All agents use this service. Falls back to OpenRouter if Gemini
rate limit is hit. Costs: $0 for all Gemini 2.0 Flash calls.
"""

from collections.abc import AsyncIterator

from app.config import get_settings


# Track which agents use which model for cost optimization
MODEL_ROUTES = {
    "strategist": "gemini/gemini-2.0-flash",
    "copywriter": "gemini/gemini-2.0-flash",
    "visual_director": "gemini/gemini-2.0-flash",
    "designer": "gemini/gemini-2.0-flash",
    "quality_check": "gemini/gemini-2.0-flash",
    "token_generator": "gemini/gemini-2.5-flash",
}


async def call_llm(
    agent_role: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 2000,
) -> str:
    """Call the LLM for a given agent role.

    Uses Gemini 2.0 Flash for most agents (free tier).
    Uses Gemini 2.5 Flash for token generation (needs more reasoning).
    Falls back to OpenRouter if Gemini fails.

    Args:
        agent_role: Must be a key in MODEL_ROUTES.
        system_prompt: System-level instructions.
        user_prompt: The user/agent message.
        temperature: 0.0-1.0
        max_tokens: Maximum output tokens.

    Returns:
        The model's response text.
    """
    settings = get_settings()
    model = MODEL_ROUTES.get(agent_role, "gemini/gemini-2.0-flash")

    try:
        return await _call_gemini(
            api_key=settings.gemini_api_key,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as gemini_error:
        if settings.openrouter_api_key:
            return await _call_openrouter(
                api_key=settings.openrouter_api_key,
                model=model,
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
    """Stream response from LLM.

    Yields text chunks as they arrive from the model.
    """
    settings = get_settings()
    model = MODEL_ROUTES.get(agent_role, "gemini/gemini-2.0-flash")

    try:
        async for chunk in _call_gemini_stream(
            api_key=settings.gemini_api_key,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield chunk
    except Exception as gemini_error:
        if settings.openrouter_api_key:
            async for chunk in _call_openrouter_stream(
                api_key=settings.openrouter_api_key,
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                yield chunk
        else:
            raise gemini_error


async def _call_gemini(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
) -> str:
    if not api_key:
        msg = "GEMINI_API_KEY not configured. Get a free key from https://aistudio.google.com/app/apikey"
        raise ValueError(msg)
    from google import genai
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model.replace("gemini/", ""),
        contents=user_prompt,
        config={
            "system_instruction": system_prompt,
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        },
    )
    return response.text


async def _call_gemini_stream(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
) -> AsyncIterator[str]:
    from google import genai
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content_stream(
        model=model.replace("gemini/", ""),
        contents=user_prompt,
        config={
            "system_instruction": system_prompt,
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        },
    )
    for chunk in response:
        if chunk.text:
            yield chunk.text


async def _call_openrouter(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
) -> str:
    import openai
    client = openai.AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )
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
    client = openai.AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )
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
