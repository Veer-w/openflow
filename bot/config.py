from __future__ import annotations

import json
from configparser import ConfigParser
from pathlib import Path

import yaml


class AppConfig:
    def __init__(self) -> None:
        parser = ConfigParser()
        package_root = Path(__file__).resolve().parent.parent
        config_path = package_root / "config.ini"
        parser.read(config_path)
        if not parser.sections():
            parser.read(Path("config.ini"))
        self._parser = parser
        prompts_path = package_root / "prompts.yaml"
        self._prompts = self._load_prompts(prompts_path)

    def agent_defaults(self) -> dict[str, object]:
        single_prompt = self._prompts.get("single_agent", {})
        prompt_text = (
            single_prompt.get("system_prompt")
            if isinstance(single_prompt, dict)
            else None
        )
        return {
            "model": self._get_str("agent_defaults", "model", "qwen2.5:1.5b"),
            "system_prompt": self._get_str(
                "agent_defaults",
                "system_prompt",
                prompt_text
                if isinstance(prompt_text, str)
                else "You are a helpful workflow agent.",
            ),
            "input_field": self._get_str("agent_defaults", "input_field", "message"),
            "num_ctx": self._get_int("agent_defaults", "num_ctx", 1024),
            "num_predict": self._get_int("agent_defaults", "num_predict", 128),
            "temperature": self._get_float("agent_defaults", "temperature", 0.2),
            "tools": self._get_csv("agent_defaults", "tools", ["calculator", "utc_time"]),
            "max_tool_calls": self._get_int("agent_defaults", "max_tool_calls", 6),
        }

    def profile_8gb(self) -> dict[str, object]:
        return {
            "model": self._get_str("profile_8gb", "model", "qwen2.5:1.5b"),
            "num_ctx": self._get_int("profile_8gb", "num_ctx", 1024),
            "num_predict": self._get_int("profile_8gb", "num_predict", 128),
            "temperature": self._get_float("profile_8gb", "temperature", 0.2),
        }

    def agent_tool_settings(self) -> dict[str, object]:
        return {
            "allow_http_domains": self._get_csv("agent_tools", "allow_http_domains", []),
            "tavily_max_results": self._get_int("agent_tools", "tavily_max_results", 5),
        }

    def multi_agent_defaults(self) -> dict[str, object]:
        fallback_agents: list[dict[str, object]] = [
            {
                "name": "researcher",
                "system_prompt": "Find facts and references. Prefer tool usage.",
                "tools": ["tavily_search"],
            },
            {
                "name": "synthesizer",
                "system_prompt": "Create a concise final answer from prior agent outputs.",
                "tools": ["calculator", "utc_time"],
            },
        ]
        yaml_agents: list[dict[str, object]] = []
        multi_prompt = self._prompts.get("multi_agent", {})
        if isinstance(multi_prompt, dict):
            raw_agents = multi_prompt.get("agents")
            if isinstance(raw_agents, list):
                for item in raw_agents:
                    if not isinstance(item, dict):
                        continue
                    name = item.get("name")
                    system_prompt = item.get("system_prompt")
                    if isinstance(name, str) and isinstance(system_prompt, str):
                        yaml_agents.append(
                            {
                                "name": name,
                                "system_prompt": system_prompt,
                                "tools": [],
                            }
                        )
        if yaml_agents:
            fallback_agents = yaml_agents
        return {
            "model": self._get_str("multi_agent_defaults", "model", "qwen2.5:1.5b"),
            "input_field": self._get_str("multi_agent_defaults", "input_field", "message"),
            "num_ctx": self._get_int("multi_agent_defaults", "num_ctx", 1024),
            "num_predict": self._get_int("multi_agent_defaults", "num_predict", 128),
            "temperature": self._get_float("multi_agent_defaults", "temperature", 0.2),
            "max_tool_calls": self._get_int("multi_agent_defaults", "max_tool_calls", 4),
            "agents": self._get_json_list("multi_agent_defaults", "agents_json", fallback_agents),
        }

    def _get_str(self, section: str, key: str, fallback: str) -> str:
        return self._parser.get(section, key, fallback=fallback)

    def _get_int(self, section: str, key: str, fallback: int) -> int:
        return self._parser.getint(section, key, fallback=fallback)

    def _get_float(self, section: str, key: str, fallback: float) -> float:
        return self._parser.getfloat(section, key, fallback=fallback)

    def _get_csv(self, section: str, key: str, fallback: list[str]) -> list[str]:
        value = self._parser.get(section, key, fallback="")
        if not value:
            return list(fallback)
        return [part.strip() for part in value.split(",") if part.strip()]

    def _get_json_list(self, section: str, key: str, fallback: list[dict[str, object]]) -> list[dict[str, object]]:
        value = self._parser.get(section, key, fallback="")
        if not value:
            return list(fallback)
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [item for item in parsed if isinstance(item, dict)]
        except json.JSONDecodeError:
            pass
        return list(fallback)

    def _load_prompts(self, path: Path) -> dict[str, object]:
        if not path.exists():
            return {}
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return raw if isinstance(raw, dict) else {}


app_config = AppConfig()
