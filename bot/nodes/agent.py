from __future__ import annotations

from typing import Any

from ..config import app_config
from ..tooling import build_agent_tools


def _extract_text_from_agent_result(result: dict[str, Any]) -> str:
    messages = result.get("messages")
    if not isinstance(messages, list) or not messages:
        return str(result)

    last = messages[-1]
    content = getattr(last, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        if parts:
            return "\n".join(parts)

    return str(last)


def _run_single_agent(
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    tools: list[str],
    num_ctx: int,
    num_predict: int,
    temperature: float,
    max_tool_calls: int,
) -> str:
    selected_tools = build_agent_tools(tools)
    effective_prompt = system_prompt
    if "tavily_search" in tools:
        effective_prompt = (
            f"{system_prompt}\n"
            "When asked for factual, financial, company, or current-event information, "
            "use available tools before answering. If a tool fails, say that clearly."
        )

    from langchain_ollama import ChatOllama
    from langgraph.prebuilt import create_react_agent

    llm = ChatOllama(
        model=model,
        num_ctx=num_ctx,
        num_predict=num_predict,
        temperature=float(temperature),
    )
    agent = create_react_agent(model=llm, tools=selected_tools, prompt=effective_prompt)

    result = agent.invoke(
        {"messages": [{"role": "user", "content": user_prompt}]},
        {"recursion_limit": max(8, (max_tool_calls * 2) + 2)},
    )
    return _extract_text_from_agent_result(result)


def _validate_common_settings(
    model: Any,
    input_field: Any,
    num_ctx: Any,
    num_predict: Any,
    temperature: Any,
    max_tool_calls: Any,
) -> tuple[str, str, int, int, float, int]:
    if not isinstance(model, str) or not model:
        raise ValueError("agent.model must be a non-empty string")
    if not isinstance(input_field, str) or not input_field:
        raise ValueError("agent.input_field must be a non-empty string")
    if not isinstance(num_ctx, int) or num_ctx <= 0:
        raise ValueError("agent.num_ctx must be a positive integer")
    if not isinstance(num_predict, int) or num_predict <= 0:
        raise ValueError("agent.num_predict must be a positive integer")
    if not isinstance(temperature, (int, float)):
        raise ValueError("agent.temperature must be a number")
    if not isinstance(max_tool_calls, int) or max_tool_calls <= 0:
        raise ValueError("agent.max_tool_calls must be a positive integer")
    return model, input_field, num_ctx, num_predict, float(temperature), max_tool_calls


def _normalize_agent_chain(
    raw_agents: Any,
    *,
    default_model: str,
    default_prompt: str,
    default_tools: list[str],
) -> list[dict[str, Any]]:
    if raw_agents is None:
        return []
    if not isinstance(raw_agents, list) or not raw_agents:
        raise ValueError("langgraph_agent.agents must be a non-empty list")

    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_agents):
        if not isinstance(item, dict):
            raise ValueError("langgraph_agent.agents entries must be objects")
        name = item.get("name")
        system_prompt = item.get("system_prompt")
        model = item.get("model", default_model)
        tools = item.get("tools", default_tools)

        if not isinstance(model, str) or not model:
            raise ValueError("Each langgraph_agent.agents[].model must be a non-empty string")
        if system_prompt is None:
            system_prompt = default_prompt
        if not isinstance(system_prompt, str):
            raise ValueError("Each langgraph_agent.agents[].system_prompt must be a string")
        if not isinstance(tools, list) or any(not isinstance(t, str) for t in tools):
            raise ValueError("Each langgraph_agent.agents[].tools must be a list of strings")

        normalized.append(
            {
                "name": str(name) if isinstance(name, str) and name else f"agent_{idx + 1}",
                "system_prompt": system_prompt,
                "model": model,
                "tools": list(tools),
            }
        )

    return normalized


def langgraph_agent_handler(params: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Execute a LangGraph agent chain (single or sequential multi-agent) using local Ollama."""
    defaults = app_config.agent_defaults()
    model = params.get("model", defaults["model"])
    system_prompt = params.get("system_prompt", defaults["system_prompt"])
    input_field = params.get("input_field", defaults["input_field"])
    num_ctx = params.get("num_ctx", defaults["num_ctx"])
    num_predict = params.get("num_predict", defaults["num_predict"])
    temperature = params.get("temperature", defaults["temperature"])
    tools = params.get("tools", defaults.get("tools", []))
    max_tool_calls = params.get("max_tool_calls", defaults.get("max_tool_calls", 6))
    agents = params.get("agents")

    if not isinstance(system_prompt, str):
        raise ValueError("langgraph_agent.system_prompt must be a string")
    if not isinstance(tools, list) or any(not isinstance(item, str) for item in tools):
        raise ValueError("langgraph_agent.tools must be a list of tool names")
    model, input_field, num_ctx, num_predict, temperature, max_tool_calls = _validate_common_settings(
        model, input_field, num_ctx, num_predict, temperature, max_tool_calls
    )
    agent_chain = _normalize_agent_chain(
        agents,
        default_model=model,
        default_prompt=system_prompt,
        default_tools=list(tools),
    )

    prompt_value = payload.get(input_field)
    if prompt_value is None:
        raise ValueError(f"langgraph_agent expected input field '{input_field}' in payload")

    original_input = str(prompt_value)
    user_prompt = original_input

    try:
        trace: list[dict[str, Any]] = []
        if agent_chain:
            running_context = original_input
            for idx, agent_cfg in enumerate(agent_chain):
                step_input = (
                    running_context
                    if idx == 0
                    else (
                        f"Original user request:\n{original_input}\n\n"
                        f"Current context from previous agents:\n{running_context}\n\n"
                        "Continue and improve the answer."
                    )
                )
                output_text = _run_single_agent(
                    model=agent_cfg["model"],
                    system_prompt=agent_cfg["system_prompt"],
                    user_prompt=step_input,
                    tools=agent_cfg["tools"],
                    num_ctx=num_ctx,
                    num_predict=num_predict,
                    temperature=temperature,
                    max_tool_calls=max_tool_calls,
                )
                if output_text.strip():
                    running_context = output_text
                trace.append(
                    {
                        "name": agent_cfg["name"],
                        "model": agent_cfg["model"],
                        "tools": agent_cfg["tools"],
                        "output": output_text,
                    }
                )
            output_text = running_context
        else:
            output_text = _run_single_agent(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                tools=tools,
                num_ctx=num_ctx,
                num_predict=num_predict,
                temperature=temperature,
                max_tool_calls=max_tool_calls,
            )
            trace = []
    except ImportError as exc:
        raise RuntimeError(
            "Missing agent dependencies. Install with: uv add langgraph langchain-ollama"
        ) from exc

    merged = dict(payload)
    merged["agent_output"] = output_text
    merged["agent_model"] = model
    merged["agent_num_ctx"] = num_ctx
    merged["agent_num_predict"] = num_predict
    merged["agent_tools"] = tools
    if trace:
        merged["agent_trace"] = trace
        merged["agent_count"] = len(trace)
    return merged


def multi_agent_handler(params: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Legacy compatibility shim. Uses langgraph_agent with an agents chain."""
    defaults = app_config.multi_agent_defaults()
    proxy_params = dict(params)
    proxy_params.setdefault("model", defaults["model"])
    proxy_params.setdefault("input_field", defaults["input_field"])
    proxy_params.setdefault("num_ctx", defaults["num_ctx"])
    proxy_params.setdefault("num_predict", defaults["num_predict"])
    proxy_params.setdefault("temperature", defaults["temperature"])
    proxy_params.setdefault("max_tool_calls", defaults["max_tool_calls"])
    proxy_params.setdefault("agents", defaults["agents"])
    merged = langgraph_agent_handler(proxy_params, payload)
    merged["multi_agent_output"] = merged.get("agent_output")
    if "agent_trace" in merged:
        merged["multi_agent_trace"] = merged["agent_trace"]
        merged["multi_agent_count"] = merged.get("agent_count", 0)
    return merged
