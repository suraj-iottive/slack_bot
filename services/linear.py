import logging
import os
import requests
from typing import Dict, Any, Optional
from config import settings

logger = logging.getLogger(__name__)

class LinearService:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or getattr(settings, "LINEAR_API_KEY", "") or os.environ.get("LINEAR_API_KEY", "")
        # Remove placeholder if present
        if self.api_key and self.api_key.endswith("-placeholder"):
            self.api_key = ""
        self.base_url = "https://api.linear.app/graphql"

    def get_issue(self, issue_key: str) -> Optional[Dict[str, Any]]:
        """
        Queries Linear API to retrieve issue details (title and url).
        """
        if not self.api_key:
            logger.warning("Linear API key is not configured. Cannot query Linear.")
            return None

        query = """
        query GetIssue($id: String!) {
            issue(id: $id) {
                title
                url
            }
        }
        """
        payload = {
            "query": query,
            "variables": {"id": issue_key}
        }
        headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(self.base_url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            res_json = response.json()
            if "errors" in res_json:
                logger.error(f"Linear GraphQL errors for key {issue_key}: {res_json['errors']}")
                return None
            return res_json.get("data", {}).get("issue")
        except Exception as e:
            logger.error(f"Failed to query Linear issue {issue_key}: {e}")
            return None
