from __future__ import annotations

import json
from typing import Any
from urllib import error, request

from .models import PlannerConfig


def generate_with_model(
    *,
    system_prompt: str,
    user_prompt: str,
    config: PlannerConfig,
    temperature: float,
    max_tokens: int,
    expect_json: bool,
) -> dict[str, Any] | None:
    # 主调用入口：Ollama 走原生接口，其他模型路由再回退到 LiteLLM。
    if config.model.startswith("ollama/"):
        return _generate_with_ollama_chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            config=config,
            temperature=temperature,
            max_tokens=max_tokens,
            expect_json=expect_json,
        )

    return _generate_with_litellm(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        config=config,
        temperature=temperature,
        max_tokens=max_tokens,
        expect_json=expect_json,
    )


def _generate_with_ollama_chat(
    *,
    system_prompt: str,
    user_prompt: str,
    config: PlannerConfig,
    temperature: float,
    max_tokens: int,
    expect_json: bool,
) -> dict[str, Any] | None:
    # 这里绕过 LiteLLM，直接打 Ollama 原生 /api/chat，避免兼容层把 content 变空。
    model = config.model.split("/", 1)[1]
    api_base = config.api_base.rstrip("/")
    if api_base.endswith("/v1"):
        api_base = api_base[:-3]
    endpoint = f"{api_base}/api/chat"

    payload: dict[str, Any] = {
        "model": model,
        "stream": False,
        # `think:false` 可以明显减少长思考占用，让正文更容易返回。
        "think": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        endpoint,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with request.urlopen(req, timeout=config.request_timeout_sec) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        content = data.get("message", {}).get("content", "")
        if not content:
            return None
        if expect_json:
            parsed = _parse_json_content(content)
            return parsed
        return {"text": content}
    except (error.URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError):
        return None


def _generate_with_litellm(
    *,
    system_prompt: str,
    user_prompt: str,
    config: PlannerConfig,
    temperature: float,
    max_tokens: int,
    expect_json: bool,
) -> dict[str, Any] | None:
    try:
        from litellm import completion
    except Exception:
        return None

    try:
        kwargs: dict[str, Any] = {
            "model": config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "api_base": config.api_base,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if expect_json:
            kwargs["response_format"] = {"type": "json_object"}
        response = completion(**kwargs)
        content = response.choices[0].message.content
        if not content:
            return None
        if expect_json:
            return json.loads(content)
        return {"text": content}
    except Exception:
        return None


def _parse_json_content(content: str) -> dict[str, Any] | None:
    # 兼容模型偶尔夹带解释文本的情况，尽量从正文中截取 JSON。
    content = content.strip()
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # Fallback: extract first JSON object block from mixed text.
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    candidate = content[start : end + 1]
    try:
        data = json.loads(candidate)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        return None
    return None
