import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import logging
log = logging.getLogger(__name__)


class CommandStatusError(Exception):
    pass


class Command:
    def __init__(
            self,
            command="",
            channel="",
            message="",
            files=[],
            args={},
            callback=None):
        self.command = command
        self.channel = channel
        self.message = message
        self.files = files
        self.args = args

    def respond(self):
        if os.environ.get("SLACK_BOT_TOKEN"):
            client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
        else:
            log.warning("Environment value 'SLACK_BOT_TOKEN' is not difined")
            return

        if self.files:
            for file in self.files:
                log.debug(f"result file: {file}")
                try:
                    client.files_upload(
                        channels=self.channel,
                        file=file,
                        title=self.message,
                    )
                except SlackApiError as e:
                    log.error(e.response["error"])
        else:
            try:
                client.chat_postMessage(
                    channel=self.channel,
                    text=self.message,
                )
            except SlackApiError as e:
                log.error(e.response["error"])
