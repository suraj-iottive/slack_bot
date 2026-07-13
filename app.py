import logging
# pyrefly: ignore [missing-import]
from fastapi import FastAPI, Request, Depends, BackgroundTasks, Form, HTTPException
# pyrefly: ignore [missing-import]
from fastapi.responses import JSONResponse, Response
from typing import Optional
import json

from config import settings
from services.auth import verify_slack_signature
from services.parser import parse_slash_command, parse_interactive_payload
from services.bitrise import BitriseService
from services.slack import SlackService
from services.canvas import CanvasService
from services.release_generator import ReleaseGenerator



# Setup logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="simplehuman Release Bot",
    description="Slack integration for triggering and monitoring Bitrise builds",
    version="1.0.0"
)

# Instantiate services
slack_service = SlackService()
bitrise_service = BitriseService()

@app.get("/health")
def health_check():
    return {"status": "ok", "app": "simplehuman-release-bot"}

# Background task for direct trigger slash command (e.g. /release trigger android main)
def process_direct_trigger(platform: str, ref: str, response_url: str):
    logger.info(f"Background task: triggering build for {platform} on branch {ref}")
    # Map platform to configured workflows
    if platform == "android":
        workflow_id = settings.ANDROID_WORKFLOW
    elif platform == "ios":
        workflow_id = settings.IOS_WORKFLOW
    else:
        workflow_id = platform
    
    try:
        slack_service.send_delayed_response(
            response_url,
            text=f"⏳ Contacting Bitrise to trigger `{workflow_id}` build for `{platform}` on branch `{ref}`...",
            ephemeral=True
        )
        
        result = bitrise_service.trigger_build(
            workflow_id=workflow_id,
            branch=ref,
            commit_message=f"Triggered via Slack Command: /release trigger {platform} {ref}"
        )
        
        if "error" in result:
            slack_service.send_delayed_response(
                response_url,
                text=f"❌ Failed to trigger build: {result['error']}",
                ephemeral=True
            )
            return

        build_data = result.get("build_params", {})
        build_slug = result.get("build_slug")
        build_number = result.get("build_number")
        
        # Build standard status blocks
        full_build_data = {
            "status": 0,  # In Progress
            "build_url": result.get("build_url"),
            "build_number": build_number,
            "triggered_workflow": workflow_id,
            "branch": ref,
            "slug": build_slug,
            "commit_message": f"Triggered via Slack Release Bot Command",
            "triggered_by": "Slack Release Bot"
        }
        
        slack_service.send_delayed_response(
            response_url,
            blocks=slack_service.build_build_status_blocks(full_build_data),
            replace_original=False
        )
        
    except Exception as e:
        logger.error(f"Error in process_direct_trigger background task: {e}")
        slack_service.send_delayed_response(
            response_url,
            text=f"❌ An error occurred: {str(e)}",
            ephemeral=True
        )

# Background task for listing build status
def process_status_request(build_slug: Optional[str], response_url: str):
    try:
        if build_slug:
            slack_service.send_delayed_response(
                response_url,
                text=f"⏳ Fetching status for build `{build_slug}`...",
                ephemeral=True
            )
            build_data = bitrise_service.get_build(build_slug)
            blocks = slack_service.build_build_status_blocks(build_data)
            slack_service.send_delayed_response(response_url, blocks=blocks)
        else:
            slack_service.send_delayed_response(
                response_url,
                text="⏳ Fetching recent builds...",
                ephemeral=True
            )
            builds = bitrise_service.list_builds(limit=5)
            if not builds:
                slack_service.send_delayed_response(response_url, text="No builds found.", ephemeral=True)
                return
            
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "📊 Recent Bitrise Builds",
                        "emoji": True
                    }
                }
            ]
            for b in builds:
                status_emoji = "⏳"
                status_str = "In Progress"
                if b.get("status") == 1:
                    status_emoji = "✅"
                    status_str = "Success"
                elif b.get("status") == 2:
                    status_emoji = "❌"
                    status_str = "Failed"
                elif b.get("status") == 3:
                    status_emoji = "⚠️"
                    status_str = "Aborted"

                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*{status_emoji} Build #{b.get('build_number')}* - {status_str}\n"
                            f"Workflow: `{b.get('triggered_workflow')}` | Branch: `{b.get('branch')}`\n"
                            f"Slug: `{b.get('slug')}` | <{b.get('build_url')}|View Build>"
                        )
                    }
                })
            slack_service.send_delayed_response(response_url, blocks=blocks)
    except Exception as e:
        logger.error(f"Error in process_status_request: {e}")
        slack_service.send_delayed_response(
            response_url,
            text=f"❌ Failed to fetch build status: {str(e)}",
            ephemeral=True
        )

# Background task for aborting build
def process_abort_request(build_slug: str, response_url: str):
    try:
        slack_service.send_delayed_response(
            response_url,
            text=f"⏳ Aborting build `{build_slug}`...",
            ephemeral=True
        )
        res = bitrise_service.abort_build(build_slug)
        if res.get("status") == "ok":
            slack_service.send_delayed_response(
                response_url,
                text=f"✅ Successfully requested abortion for build `{build_slug}`.",
                ephemeral=True
            )
        else:
            slack_service.send_delayed_response(
                response_url,
                text=f"❌ Failed to abort build: {res.get('error', 'Unknown error')}",
                ephemeral=True
            )
    except Exception as e:
        logger.error(f"Error in process_abort_request: {e}")
        slack_service.send_delayed_response(
            response_url,
            text=f"❌ Failed to abort build: {str(e)}",
            ephemeral=True
        )

# Background task to process interactive form submission
def process_interactive_trigger(payload: dict):
    response_url = payload.get("response_url")
    state_values = payload.get("state", {}).get("values", {})
    
    # Locate form values
    platform = None
    workflow = None
    branch = "main"

    try:
        # Extract selected values from Block Kit structure
        for block_id, actions in state_values.items():
            if "platform_select" in actions:
                platform = actions["platform_select"].get("selected_option", {}).get("value")
            if "workflow_select" in actions:
                workflow = actions["workflow_select"].get("selected_option", {}).get("value")
            if "branch_input" in actions:
                branch = actions["branch_input"].get("value", "main")

        if not platform or not workflow:
            slack_service.send_delayed_response(
                response_url,
                text="❌ Please make sure to select both Platform and Workflow.",
                ephemeral=True
            )
            return

        slack_service.send_delayed_response(
            response_url,
            text=f"⏳ Starting `{workflow}` build for `{platform}` on branch `{branch}`...",
            replace_original=True
        )

        result = bitrise_service.trigger_build(
            workflow_id=workflow,
            branch=branch,
            commit_message=f"Triggered via Slack Interactive Release Panel",
        )

        if "error" in result:
            slack_service.send_delayed_response(
                response_url,
                text=f"❌ Failed to trigger build: {result['error']}",
                replace_original=False
            )
            return

        build_number = result.get("build_number")
        build_slug = result.get("build_slug")
        build_url = result.get("build_url")

        full_build_data = {
            "status": 0,
            "build_url": build_url,
            "build_number": build_number,
            "triggered_workflow": workflow,
            "branch": branch,
            "slug": build_slug,
            "commit_message": f"Triggered via Slack Release Bot Panel",
            "triggered_by": payload.get("user_name", "Release Bot")
        }

        # Update the original configuration panel with the triggered build card
        slack_service.send_delayed_response(
            response_url,
            blocks=slack_service.build_build_status_blocks(full_build_data),
            replace_original=True
        )

    except Exception as e:
        logger.error(f"Error in process_interactive_trigger: {e}")
        slack_service.send_delayed_response(
            response_url,
            text=f"❌ Failed to trigger build: {str(e)}",
            replace_original=False
        )

@app.post("/slack/events")
async def slack_events(request: Request):
    body = await request.json()

    # Slack URL verification
    if body.get("type") == "url_verification":
        return {"challenge": body["challenge"]}

    event = body.get("event", {})

    # Ignore non-mention events
    if event.get("type") != "app_mention":
        return {"ok": True}

    text = event.get("text", "")

    # Remove the bot mention
    bot_id = "U0BGRJ6JJDN"   # Your bot ID
    text = text.replace(f"<@{bot_id}>", "").strip()

    print("=" * 50)
    print("Command :", text)

    parts = text.split()

    print("Parts :", parts)

    platform = None
    build = None
    branch = None

    if "android" in parts:
        platform = "android"
    elif "ios" in parts:
        platform = "ios"
    elif "both" in parts:
        platform = "both"

    if "--build" in parts:
        build = parts[parts.index("--build") + 1]

    if "--branch" in parts:
        branch = parts[parts.index("--branch") + 1]

    print("Platform :", platform)
    print("Build    :", build)
    print("Branch   :", branch)

    # Select workflow
    if platform == "android":
        workflow = settings.ANDROID_WORKFLOW
    elif platform == "ios":
        workflow = settings.IOS_WORKFLOW
    elif platform == "both":
        workflow = settings.BOTH_WORKFLOW
    else:
        print("Unknown platform")
        return {"ok": True}

    print("Workflow :", workflow)

    # Trigger Bitrise
    result = bitrise_service.trigger_build(
        workflow_id=workflow,
        branch=branch,
        commit_message=f"Triggered from Slack (Build {build})",
        environments=[
            {
                "mapped_to": "BUILD_NUMBER",
                "value": build,
                "is_expand": True
            }
        ]
    )

    print(result)

    return {"ok": True}

@app.post("/slack/commands")
async def slack_commands(
    background_tasks: BackgroundTasks,
    request: Request,
    command: str = Form(...),
    text: Optional[str] = Form(None),
    response_url: str = Form(...),
    user_id: str = Form(...),
    user_name: str = Form(...),
    channel_id: str = Form(...),
    verified: bool = Depends(verify_slack_signature)
):
    """
    Main entry point for all incoming Slack Slash commands (e.g. /release).
    """
    logger.info(f"Received Slash Command: {command} with args: '{text}' from {user_name}")

    parsed = parse_slash_command(text)
    action = parsed.get("action")

    if action == "help":
        blocks = slack_service.build_help_blocks()
        return JSONResponse(content={"response_type": "ephemeral", "blocks": blocks})

    elif action == "interactive_menu":
        blocks = slack_service.build_interactive_menu_blocks()
        return JSONResponse(content={"response_type": "ephemeral", "blocks": blocks})

    elif action == "trigger":
        # Launch triggering build in background task to respond to Slack immediately (within 3 seconds)
        background_tasks.add_task(
            process_direct_trigger,
            platform=parsed["platform"],
            ref=parsed["ref"],
            response_url=response_url
        )
        return Response(content="Processing request...", status_code=200)

    elif action == "status":
        background_tasks.add_task(
            process_status_request,
            build_slug=parsed.get("build_slug"),
            response_url=response_url
        )
        return Response(content="Fetching status...", status_code=200)

    elif action == "abort":
        build_slug = parsed.get("build_slug")
        if not build_slug:
            return JSONResponse(
                content={"response_type": "ephemeral", "text": "❌ Please specify a build slug: `/release abort [build_slug]`"}
            )
        background_tasks.add_task(
            process_abort_request,
            build_slug=build_slug,
            response_url=response_url
        )
        return Response(content="Processing abort request...", status_code=200)

    return JSONResponse(
        content={"response_type": "ephemeral", "text": "❓ Unknown command. Try `/release help`"}
    )

@app.post("/slack/actions")
async def slack_actions(
    background_tasks: BackgroundTasks,
    request: Request,
    payload: str = Form(...),
    verified: bool = Depends(verify_slack_signature)
):
    """
    Handles interactive actions from Slack (button clicks, select menus).
    """
    try:
        payload_data = json.loads(payload)
    except json.JSONDecodeError:
        logger.error("Failed to parse interactive payload JSON")
        raise HTTPException(status_code=400, detail="Invalid payload")

    parsed = parse_interactive_payload(payload)
    logger.info(f"Received interactive action from {parsed.get('user_name')}")

    actions = parsed.get("actions", [])
    if not actions:
        return Response(status_code=200)

    action = actions[0]
    action_id = action.get("action_id")

    if action_id == "cancel_btn":
        # Delete or replace the panel message
        slack_service.send_delayed_response(
            parsed["response_url"],
            text="❌ Release operation cancelled.",
            replace_original=True,
            ephemeral=True
        )
        return Response(status_code=200)

    elif action_id == "trigger_release_btn":
        # Launch background build process
        background_tasks.add_task(process_interactive_trigger, payload=payload_data)
        return Response(status_code=200)

    return Response(status_code=200)

def process_release_automation(release_data: dict):
    build_number = str(release_data.get("build_number") or "")
    logger.info(f"[Release Automation] Starting background orchestration for Build #{build_number}")
    logger.info(f"[Release Automation] Payload data received: {release_data}")
    
    try:
        canvas_service = CanvasService()
        
        # 5. Check if build_number already exists in the Canvas
        logger.info(f"[Release Automation] Checking if Build #{build_number} exists in Slack Canvas...")
        if build_number and canvas_service.build_exists(build_number):
            logger.info(f"[Release Automation] Build #{build_number} already exists in Canvas. Stopping execution.")
            return

        logger.info(f"[Release Automation] Build #{build_number} does not exist in Canvas. Generating release notes...")

        # 6. Generate release notes
        release_gen = ReleaseGenerator(bitrise_service=bitrise_service)
        release_notes = release_gen.generate_release_notes(release_data)
        logger.info("[Release Automation] Release notes successfully generated.")

        # 6. Insert into canvas
        logger.info(f"[Release Automation] Inserting generated release notes into Canvas {canvas_service.canvas_id}...")
        canvas_updated = canvas_service.insert_release_notes(release_notes)
        
        if canvas_updated:
            logger.info(f"[Release Automation] Canvas successfully updated for Build #{build_number}.")
            # 7. Post release notes to the Slack channel
            channel = settings.DEFAULT_SLACK_CHANNEL
            logger.info(f"[Release Automation] Posting release notes to Slack channel {channel}...")
            slack_service.post_message(channel=channel, text=release_notes)
            logger.info("[Release Automation] Release notes successfully posted to Slack channel.")
        else:
            logger.error(f"[Release Automation] Failed to update Canvas for Build #{build_number}. Release notes were NOT posted to Slack.")
    except Exception as ex:
        logger.exception(f"[Release Automation] Error in release automation background task: {ex}")

@app.post("/webhooks/bitrise")
async def bitrise_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receives build status updates from Bitrise and broadcasts status cards to Slack.
    Configure this URL in the App settings -> Webhooks section on Bitrise.
    """
    logger.info("Received Bitrise webhook request.")
    try:
        payload = await request.json()
        logger.info(f"Webhook payload JSON: {payload}")
    except json.JSONDecodeError:
        logger.error("Invalid JSON payload received in Bitrise webhook.")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Bitrise build webhook schema has a "build" dictionary containing status details
    build_data = payload.get("build") or payload

    # Extract info needed to check status
    status = payload.get("status") or build_data.get("status")
    logger.info(f"Checking build status: {status}")

    # Only continue for successful builds
    is_success = False
    if status == 1 or status == "1" or (isinstance(status, str) and status.lower() == "success"):
        is_success = True

    if not is_success:
        logger.info(f"Ignoring non-successful build status {status}")
        return {
            "status": "ignored",
            "reason": "build not successful"
        }

    # Extract payload fields
    build_number = payload.get("build_number") or build_data.get("build_number")
    branch = payload.get("branch") or build_data.get("branch")
    workflow = payload.get("workflow") or build_data.get("workflow") or build_data.get("triggered_workflow")
    environment = payload.get("environment") or build_data.get("environment")
    release_notes = payload.get("release_notes") or build_data.get("release_notes")
    android_install_url = payload.get("android_install_url") or build_data.get("android_install_url")
    ios_install_url = payload.get("ios_install_url") or build_data.get("ios_install_url")

    if not build_number:
        logger.warning("Bitrise webhook payload does not contain build_number. Skipping.")
        return {"status": "skipped", "reason": "no build_number"}

    logger.info(f"Extracted webhook values: build_number={build_number}, branch={branch}, workflow={workflow}, environment={environment}, android_install_url={android_install_url}, ios_install_url={ios_install_url}")

    release_data = {
        "build_number": build_number,
        "branch": branch,
        "workflow": workflow,
        "environment": environment,
        "release_notes": release_notes,
        "android_install_url": android_install_url,
        "ios_install_url": ios_install_url
    }

    logger.info(f"Scheduling release automation background task for Build #{build_number}...")
    background_tasks.add_task(process_release_automation, release_data)

    return {"status": "success", "info": "release automation queued"}
