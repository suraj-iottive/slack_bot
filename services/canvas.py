import logging
import os
from typing import Optional
# pyrefly: ignore [missing-import]
from slack_sdk import WebClient
# pyrefly: ignore [missing-import]
from slack_sdk.errors import SlackApiError
from config import settings

logger = logging.getLogger(__name__)

class CanvasService:
    def __init__(self, token: str = None, canvas_id: str = None):
        self.token = token or settings.SLACK_BOT_TOKEN
        # Fallback to None if placeholder is present to prevent API errors in mock modes
        if self.token and self.token.endswith("-placeholder"):
            self.token = ""
        self.canvas_id = canvas_id or getattr(settings, "SLACK_CANVAS_ID", "") or os.environ.get("SLACK_CANVAS_ID", "")
        # Remove placeholder if present
        if self.canvas_id and self.canvas_id.endswith("-placeholder"):
            self.canvas_id = ""
        self.client = WebClient(token=self.token) if self.token else None

    def build_exists(self, build_number: str) -> bool:
        """
        Checks if the build number already exists in the Canvas.
        """
        if not self.client:
            logger.warning("Slack client not initialized for CanvasService.")
            return False
        if not self.canvas_id:
            logger.warning("Slack Canvas ID not configured.")
            return False

        try:
            # We search for the exact build number text pattern we write
            response = self.client.canvases_sections_lookup(
                canvas_id=self.canvas_id,
                criteria={
                    "contains_text": f"Build Number: {build_number}"
                }
            )
            sections = response.get("sections", [])
            return len(sections) > 0
        except SlackApiError as e:
            logger.error(f"Slack API error checking build existence in canvas: {e.response['error']}")
            return False
        except Exception as e:
            logger.error(f"Failed to check if build exists in canvas: {e}")
            return False

    def insert_release_notes(self, release_notes: str) -> bool:
        """
        Inserts the generated release notes at the TOP of the Slack Canvas.
        """
        if not self.client:
            logger.warning("Slack client not initialized for CanvasService.")
            return False
        if not self.canvas_id:
            logger.warning("Slack Canvas ID not configured.")
            return False

        try:
            content = f"{release_notes}\n\n---\n\n"
            response = self.client.canvases_edit(
                canvas_id=self.canvas_id,
                changes=[
                    {
                        "operation": "insert_at_start",
                        "document_content": {
                            "type": "markdown",
                            "markdown": content
                        }
                    }
                ]
            )
            return response.get("ok", False)
        except SlackApiError as e:
            logger.error(f"Slack API error inserting release notes into canvas: {e.response['error']}")
            return False
        except Exception as e:
            logger.error(f"Failed to insert release notes into Slack Canvas: {e}")
            return False
