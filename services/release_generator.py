import os
import re
import datetime
import logging
from typing import Dict, Any, Optional
from services.linear import LinearService
from services.bitrise import BitriseService

logger = logging.getLogger(__name__)

class ReleaseGenerator:
    def __init__(self, linear_service: Optional[LinearService] = None, bitrise_service: Optional[BitriseService] = None):
        self.linear_service = linear_service or LinearService()
        self.bitrise_service = bitrise_service or BitriseService()

    def generate_release_notes(self, build_data: Dict[str, Any]) -> str:
        """
        Generates the formatted release notes from Bitrise build details.
        """
        # Read release_notes from build_data
        raw_notes = build_data.get("release_notes") or ""
        if isinstance(raw_notes, str):
            raw_notes = raw_notes.strip()

        # Query Linear API to convert issue keys to links: e.g. MOB-7 to <MOB-7 URL|MOB-7>: Issue Title
        formatted_notes = self.convert_linear_issues(raw_notes)

        # Get values from build_data
        build_number = build_data.get("build_number", "N/A")
        environment = build_data.get("environment", "Stage")
        android_install_url = build_data.get("android_install_url", "N/A")
        ios_install_url = build_data.get("ios_install_url", "N/A")

        # Today's Date
        today_str = datetime.date.today().strftime("%Y-%m-%d")

        # Format layout:
        # Date: <today>
        #
        # Environment: <environment>
        #
        # Build Number: <build_number>
        #
        # <release_notes>
        #
        # CI/CD
        #
        # * Bitrise [<build_number>]
        #   Link ==> <android_install_url>
        #
        # * TestFlight [<build_number>]
        #   Link ==> <ios_install_url>
        #
        # @Erin @MSchultz @Fernando @achan
        
        notes_format = (
            f"Date: {today_str}\n\n"
            f"Environment: {environment}\n\n"
            f"Build Number: {build_number}\n\n"
            f"{formatted_notes}\n\n"
            f"CI/CD\n\n"
            f"* Bitrise [{build_number}]\n"
            f"  Link ==> {android_install_url}\n\n"
            f"* TestFlight [{build_number}]\n"
            f"  Link ==> {ios_install_url}\n\n"
            f"@Erin @MSchultz @Fernando @achan"
        )
        return notes_format

    def convert_linear_issues(self, text: str) -> str:
        # Match issue keys: e.g. MOB-7, SI-10, ENG-123
        pattern = r'\b([A-Z]+-\d+)\b'
        keys = list(set(re.findall(pattern, text)))
        
        for key in keys:
            try:
                issue = self.linear_service.get_issue(key)
                if issue and issue.get("title") and issue.get("url"):
                    url = issue["url"]
                    title = issue["title"]
                    # Slack markdown link: <url|key>: title
                    formatted = f"<{url}|{key}>: {title}"
                    text = re.sub(rf'\b{re.escape(key)}\b', formatted, text)
                else:
                    logger.warning(f"Could not retrieve details for Linear issue {key}")
            except Exception as e:
                logger.error(f"Error querying Linear for {key}: {e}")
        return text
