import logging
import requests
from typing import Dict, Any, List, Optional
# pyrefly: ignore [missing-import]
from slack_sdk import WebClient
# pyrefly: ignore [missing-import]
from slack_sdk.errors import SlackApiError
from config import settings

logger = logging.getLogger(__name__)

class SlackService:
    def __init__(self, token: str = None):
        self.token = token or settings.SLACK_BOT_TOKEN
        # Fallback to None if placeholder is present to prevent API errors in mock modes
        if self.token and self.token.endswith("-placeholder"):
            self.token = ""
        self.client = WebClient(token=self.token) if self.token else None

    def post_message(self, channel: str, text: Optional[str] = None, blocks: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
        """
        Sends a public message to a Slack channel.
        """
        if not self.client:
            logger.warning(f"Slack client not configured. Message would have been: {text or blocks}")
            return None

        try:
            response = self.client.chat_postMessage(
                channel=channel,
                text=text or "Update from simplehuman-release-bot",
                blocks=blocks
            )
            return response.data
        except SlackApiError as e:
            logger.error(f"Slack API error posting message: {e.response['error']}")
            raise

    def post_ephemeral(self, channel: str, user_id: str, text: Optional[str] = None, blocks: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
        """
        Sends an ephemeral message (only visible to one user) in a channel.
        """
        if not self.client:
            logger.warning(f"Slack client not configured. Ephemeral to {user_id}: {text or blocks}")
            return None

        try:
            response = self.client.chat_postEphemeral(
                channel=channel,
                user=user_id,
                text=text or "Ephemeral update from simplehuman-release-bot",
                blocks=blocks
            )
            return response.data
        except SlackApiError as e:
            logger.error(f"Slack API error posting ephemeral message: {e.response['error']}")
            raise

    def send_delayed_response(
        self,
        response_url: str,
        text: Optional[str] = None,
        blocks: Optional[List[Dict[str, Any]]] = None,
        replace_original: bool = False,
        ephemeral: bool = False
    ) -> bool:
        """
        Sends a response back to Slack using a temporary response_url.
        Used for slash command delayed responses (up to 30 min) and interactive actions.
        """
        payload: Dict[str, Any] = {}
        if text:
            payload["text"] = text
        if blocks:
            payload["blocks"] = blocks
            
        payload["replace_original"] = replace_original
        
        if ephemeral:
            payload["response_type"] = "ephemeral"
        else:
            payload["response_type"] = "in_channel"

        try:
            response = requests.post(response_url, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            logger.error(f"Failed to post to Slack response_url: {e}")
            return False

    def build_help_blocks(self) -> List[Dict[str, Any]]:
        """
        Returns Block Kit blocks explaining command usage.
        """
        return [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🤖 Release Bot Command Center",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "Manage your mobile app releases on Bitrise directly from Slack. "
                        "Here are the commands you can use:\n\n"
                        "• `/release` - Opens the interactive release panel to configure and trigger builds.\n"
                        "• `/release trigger <platform> <branch>` - Directly triggers a release build.\n"
                        "  _Examples: `/release trigger android main`, `/release trigger ios release/v2.1`_\n"
                        "• `/release status <build_slug>` - Checks the status of a specific build.\n"
                        "• `/release status` - Fetches the last 5 builds.\n"
                        "• `/release abort <build_slug>` - Cancels an active build.\n"
                        "• `/release help` - Displays this help message."
                    )
                }
            }
        ]

    def build_interactive_menu_blocks(self) -> List[Dict[str, Any]]:
        """
        Generates the standard interactive menu panel for release configurations.
        """
        return [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🚀 Trigger New Bitrise Build",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Configure and start a mobile app deployment workflow."
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "input",
                "block_id": "platform_block",
                "element": {
                    "type": "static_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select Platform",
                        "emoji": True
                    },
                    "options": [
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "🤖 Android",
                                "emoji": True
                            },
                            "value": "android"
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "🍎 iOS",
                                "emoji": True
                            },
                            "value": "ios"
                        }
                    ],
                    "action_id": "platform_select"
                },
                "label": {
                    "type": "plain_text",
                    "text": "Platform",
                    "emoji": True
                }
            },
            {
                "type": "input",
                "block_id": "workflow_block",
                "element": {
                    "type": "static_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select Workflow",
                        "emoji": True
                    },
                    "options": [
                        {
                            "text": {
                                "type": "plain_text",
                                "text": f"Android: {settings.ANDROID_WORKFLOW}",
                                "emoji": True
                            },
                            "value": settings.ANDROID_WORKFLOW
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": f"iOS: {settings.IOS_WORKFLOW}",
                                "emoji": True
                            },
                            "value": settings.IOS_WORKFLOW
                        }
                    ],
                    "action_id": "workflow_select"
                },
                "label": {
                    "type": "plain_text",
                    "text": "Workflow",
                    "emoji": True
                }
            },
            {
                "type": "input",
                "block_id": "branch_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "branch_input",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "e.g. main, release/v1.0"
                    },
                    "initial_value": "main"
                },
                "label": {
                    "type": "plain_text",
                    "text": "Git Ref (Branch/Tag/Commit)",
                    "emoji": True
                }
            },
            {
                "type": "actions",
                "block_id": "actions_block",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Trigger Release",
                            "emoji": True
                        },
                        "style": "primary",
                        "value": "trigger_release_submit",
                        "action_id": "trigger_release_btn",
                        "confirm": {
                            "title": {
                                "type": "plain_text",
                                "text": "Confirm Release Trigger"
                            },
                            "text": {
                                "type": "plain_text",
                                "text": "Are you sure you want to trigger this build workflow on Bitrise?"
                            },
                            "confirm": {
                                "type": "plain_text",
                                "text": "Yes, Trigger"
                            },
                            "deny": {
                                "type": "plain_text",
                                "text": "Cancel"
                            }
                        }
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Cancel",
                            "emoji": True
                        },
                        "value": "cancel_interactive",
                        "action_id": "cancel_btn"
                    }
                ]
            }
        ]

    def build_build_status_blocks(self, build_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Builds a Block Kit message representation of a Bitrise build.
        """
        # Status mappings:
        # 0 = Not finished, 1 = Success, 2 = Failed, 3 = Aborted
        status_code = build_data.get("status")
        build_url = build_data.get("build_url", "#")
        build_number = build_data.get("build_number", "N/A")
        branch = build_data.get("branch", "N/A")
        workflow = build_data.get("triggered_workflow", "N/A")
        commit_msg = build_data.get("commit_message", "No commit message")
        
        status_emoji = "⏳"
        status_text = "In Progress"
        status_color = "#3AA3E3"  # Blue

        if status_code == 1:
            status_emoji = "✅"
            status_text = "Success"
            status_color = "#2EB886"  # Green
        elif status_code == 2:
            status_emoji = "❌"
            status_text = "Failed"
            status_color = "#A30200"  # Red
        elif status_code == 3:
            status_emoji = "⚠️"
            status_text = "Aborted"
            status_color = "#E0A100"  # Yellow

        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{status_emoji} Bitrise Build #{build_number} - {status_text}*"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Workflow:*\n`{workflow}`"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Branch:*\n`{branch}`"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Build Slug:*\n`{build_data.get('slug', 'N/A')}`"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Triggered By:*\n`{build_data.get('triggered_by', 'release-bot')}`"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Commit Message:*\n{commit_msg}"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View Build Details",
                            "emoji": True
                        },
                        "url": build_url
                    }
                ]
            }
        ]
