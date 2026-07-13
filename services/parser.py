import json
import logging
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

def parse_slash_command(text: str) -> Dict[str, Any]:
    """
    Parses the 'text' portion of a Slack slash command.
    Example text formats:
      - 'help' -> {'action': 'help'}
      - 'status' -> {'action': 'status'}
      - 'trigger android main' -> {'action': 'trigger', 'platform': 'android', 'ref': 'main'}
      - 'abort build_slug_123' -> {'action': 'abort', 'build_slug': 'build_slug_123'}
    """
    if not text or not text.strip():
        return {"action": "interactive_menu"}  # Default to showing menu if no args

    parts = text.strip().split()
    action = parts[0].lower()

    if action == "help":
        return {"action": "help"}
    
    elif action == "status":
        build_slug = parts[1] if len(parts) > 1 else None
        return {"action": "status", "build_slug": build_slug}

    elif action in ("trigger", "release"):
        # Expecting: trigger [platform] [ref]
        platform = parts[1].lower() if len(parts) > 1 else "android"
        ref = parts[2] if len(parts) > 2 else "main"
        return {
            "action": "trigger",
            "platform": platform,
            "ref": ref
        }

    elif action == "abort":
        # Expecting: abort [build_slug]
        build_slug = parts[1] if len(parts) > 1 else None
        return {
            "action": "abort",
            "build_slug": build_slug
        }

    # Fallback to help
    return {"action": "help", "invalid_command": parts[0]}


def parse_interactive_payload(payload_str: str) -> Dict[str, Any]:
    """
    Parses Slack's interactive callback payload JSON string.
    Extracts action details, user information, response URL, and values.
    """
    try:
        payload = json.loads(payload_str)
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"Failed to decode interactive payload: {e}")
        return {}

    parsed = {
        "type": payload.get("type"),
        "user_id": payload.get("user", {}).get("id"),
        "user_name": payload.get("user", {}).get("name"),
        "channel_id": payload.get("channel", {}).get("id"),
        "response_url": payload.get("response_url"),
        "trigger_id": payload.get("trigger_id"),
        "actions": []
    }

    # Extract block actions
    actions_list = payload.get("actions", [])
    for action in actions_list:
        action_data = {
            "action_id": action.get("action_id"),
            "block_id": action.get("block_id"),
            "type": action.get("type"),
            "value": action.get("value")
        }
        
        # Handle select menus
        if action.get("type") in ("static_select", "external_select"):
            action_data["selected_value"] = action.get("selected_option", {}).get("value")
        # Handle multi-select
        elif action.get("type") == "multi_static_select":
            selected_options = action.get("selected_options", [])
            action_data["selected_values"] = [opt.get("value") for opt in selected_options]
            
        parsed["actions"].append(action_data)

    return parsed
