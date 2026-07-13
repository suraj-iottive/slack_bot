import hmac
import hashlib
import time
import logging
from fastapi import Request, HTTPException
from config import settings

logger = logging.getLogger(__name__)

async def verify_slack_signature(request: Request) -> bool:
    """
    FastAPI dependency to verify signature of incoming requests from Slack.
    Uses HMAC-SHA256 signature verification protocol specified by Slack:
    https://api.slack.com/authentication/verifying-requests-from-slack
    """
    signing_secret = settings.SLACK_SIGNING_SECRET
    
    # If the secret is not configured, warn and pass (for local testing/dev)
    if not signing_secret or signing_secret.endswith("-placeholder"):
        logger.warning("SLACK_SIGNING_SECRET is not configured or is placeholder. Skipping signature verification.")
        return True

    # Read Slack headers
    slack_signature = request.headers.get("X-Slack-Signature")
    slack_timestamp = request.headers.get("X-Slack-Request-Timestamp")

    if not slack_signature or not slack_timestamp:
        logger.error("Missing Slack signature headers.")
        raise HTTPException(status_code=401, detail="Missing verification headers")

    # Verify that the request timestamp is not too old (replay attack protection)
    try:
        timestamp_diff = abs(time.time() - int(slack_timestamp))
        if timestamp_diff > 60 * 5:  # 5 minutes
            logger.error(f"Replay attack check failed: timestamp difference is {timestamp_diff} seconds.")
            raise HTTPException(status_code=401, detail="Request timestamp expired")
    except ValueError:
        logger.error("Invalid X-Slack-Request-Timestamp header.")
        raise HTTPException(status_code=401, detail="Invalid timestamp format")

    # Slack sends command payloads as form-encoded data.
    # To check the body without consuming the request stream permanently,
    # we can read the raw body.
    body = await request.body()
    body_str = body.decode("utf-8")

    # Reconstruct signature base string
    sig_basestring = f"v0:{slack_timestamp}:{body_str}".encode("utf-8")
    
    # Compute signature
    computed_sig = "v0=" + hmac.new(
        key=signing_secret.encode("utf-8"),
        msg=sig_basestring,
        digestmod=hashlib.sha256
    ).hexdigest()

    # Compare signatures in constant time
    if not hmac.compare_digest(computed_sig, slack_signature):
        logger.error("Verification failed: computed signature does not match header.")
        raise HTTPException(status_code=401, detail="Invalid request signature")

    return True
