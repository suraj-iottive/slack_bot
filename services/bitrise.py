import requests
import logging
from typing import Dict, Any, List, Optional
from config import settings

logger = logging.getLogger(__name__)

class BitriseService:
    def __init__(self, api_token: str = None, app_slug: str = None):
        self.api_token = api_token or settings.BITRISE_TOKEN
        self.app_slug = app_slug or settings.BITRISE_APP_SLUG
        self.base_url = "https://api.bitrise.io/v0.1"

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "Authorization": self.api_token,
            "Content-Type": "application/json"
        }

    def trigger_build(
        self,
        workflow_id: str,
        branch: str,
        commit_hash: Optional[str] = None,
        environments: Optional[List[Dict[str, Any]]] = None,
        commit_message: str = "Triggered via Slack Release Bot"
    ) -> Dict[str, Any]:
        """
        Triggers a new build on Bitrise.
        https://api-docs.bitrise.io/#/builds/build-trigger
        """
        if not self.api_token or self.api_token.endswith("-placeholder"):
            raise ValueError("Bitrise API token is not configured.")
        if not self.app_slug or self.app_slug.endswith("-placeholder"):
            raise ValueError("Bitrise app slug is not configured.")

        url = f"{self.base_url}/apps/{self.app_slug}/builds"
        
        build_params: Dict[str, Any] = {
            "branch": branch,
            "workflow_id": workflow_id,
            "commit_message": commit_message
        }
        
        if commit_hash:
            build_params["commit_hash"] = commit_hash
            
        if environments:
            build_params["environments"] = environments

        payload = {
            "hook_info": {
                "type": "bitrise"
            },
            "build_params": build_params,
            "triggered_by": "simplehuman-release-bot"
        }

        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to trigger Bitrise build: {e}")
            if response := getattr(e, "response", None):
                logger.error(f"Bitrise response: {response.text}")
                return {"error": response.text, "status_code": response.status_code}
            raise

    def abort_build(
        self,
        build_slug: str,
        reason: str = "Aborted via Slack Release Bot"
    ) -> Dict[str, Any]:
        """
        Aborts an active build on Bitrise.
        https://api-docs.bitrise.io/#/builds/build-abort
        """
        if not self.api_token or self.api_token.endswith("-placeholder"):
            raise ValueError("Bitrise API token is not configured.")
        if not self.app_slug or self.app_slug.endswith("-placeholder"):
            raise ValueError("Bitrise app slug is not configured.")

        url = f"{self.base_url}/apps/{self.app_slug}/builds/{build_slug}/abort"
        
        payload = {
            "abort_reason": reason,
            "abort_with_status_warning": True,
            "skip_notifications": False
        }

        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to abort Bitrise build {build_slug}: {e}")
            if response := getattr(e, "response", None):
                logger.error(f"Bitrise response: {response.text}")
                return {"error": response.text, "status_code": response.status_code}
            raise

    def get_build(self, build_slug: str) -> Dict[str, Any]:
        """
        Fetches detailed info about a specific build.
        https://api-docs.bitrise.io/#/builds/build-show
        """
        if not self.api_token or self.api_token.endswith("-placeholder"):
            raise ValueError("Bitrise API token is not configured.")
        if not self.app_slug or self.app_slug.endswith("-placeholder"):
            raise ValueError("Bitrise app slug is not configured.")

        url = f"{self.base_url}/apps/{self.app_slug}/builds/{build_slug}"

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json().get("data", {})
        except requests.RequestException as e:
            logger.error(f"Failed to get Bitrise build {build_slug}: {e}")
            raise

    def list_builds(self, limit: int = 5, status: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Lists recent builds for the configured app.
        https://api-docs.bitrise.io/#/builds/build-list
        Status values: 0 = not finished yet, 1 = successful, 2 = failed, 3 = aborted
        """
        if not self.api_token or self.api_token.endswith("-placeholder"):
            raise ValueError("Bitrise API token is not configured.")
        if not self.app_slug or self.app_slug.endswith("-placeholder"):
            raise ValueError("Bitrise app slug is not configured.")

        url = f"{self.base_url}/apps/{self.app_slug}/builds"
        params: Dict[str, Any] = {"limit": limit}
        if status is not None:
            params["status"] = status

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            return response.json().get("data", [])
        except requests.RequestException as e:
            logger.error(f"Failed to list Bitrise builds: {e}")
            raise

    def get_artifacts(self, build_slug: str) -> List[Dict[str, Any]]:
        """
        Lists all artifacts of a build.
        """
        if not self.api_token or self.api_token.endswith("-placeholder"):
            raise ValueError("Bitrise API token is not configured.")
        if not self.app_slug or self.app_slug.endswith("-placeholder"):
            raise ValueError("Bitrise app slug is not configured.")

        url = f"{self.base_url}/apps/{self.app_slug}/builds/{build_slug}/artifacts"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json().get("data", [])
        except Exception as e:
            logger.error(f"Error fetching artifacts for build {build_slug}: {e}")
            return []

    def get_artifact(self, build_slug: str, artifact_slug: str) -> Dict[str, Any]:
        """
        Retrieves details of a specific artifact.
        """
        if not self.api_token or self.api_token.endswith("-placeholder"):
            raise ValueError("Bitrise API token is not configured.")
        if not self.app_slug or self.app_slug.endswith("-placeholder"):
            raise ValueError("Bitrise app slug is not configured.")

        url = f"{self.base_url}/apps/{self.app_slug}/builds/{build_slug}/artifacts/{artifact_slug}"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json().get("data", {})
        except Exception as e:
            logger.error(f"Error fetching artifact {artifact_slug} for build {build_slug}: {e}")
            return {}

    def get_public_install_url(self, build_slug: str) -> Optional[str]:
        """
        Finds the public install page URL for the build artifacts.
        """
        try:
            artifacts = self.get_artifacts(build_slug)
            for artifact in artifacts:
                slug = artifact.get("slug")
                if slug:
                    detail = self.get_artifact(build_slug, slug)
                    url = detail.get("public_install_page_url")
                    if url:
                        return url
        except Exception as e:
            logger.error(f"Error getting public install URL: {e}")
        return None
