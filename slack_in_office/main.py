"""
Slash

Bot User OAuth Access Token - https://api.slack.com/apps/<ID>>/oauth
Verification Token - https://api.slack.com/apps/<ID>/general
"""

import logging
import os
import re
from typing import Any, Dict, List, Optional, Union

from flask import Response, jsonify
from slack import WebClient
from slack.errors import SlackApiError

logging.basicConfig(level=logging.DEBUG)


SLACK_BOT_ACCESS_TOKEN: str = os.environ["SLACK_API_TOKEN"]
SLACK_VERIFICATION_TOKEN: str = os.environ["SLACK_VERIFICATION_TOKEN"]

LOOKUP_PHRASE: str = "in the office"
PATTERN: str = LOOKUP_PHRASE.replace(" ", r"\s*")


class SlackInfo:
    def __init__(self) -> None:
        self.client = WebClient(token=SLACK_BOT_ACCESS_TOKEN)

    def get_users_list(self) -> List["User"]:
        response = self.client.users_list()
        return [
            User(
                slack_id=member["id"],
                display_name=member["profile"]["display_name"],
                status_text=member["profile"].get("status_text"),
                status_emoji=member["profile"].get("status_emoji"),
            )
            for member in response.data["members"]
            if (
                not member["is_bot"]
                and not member["deleted"]
                and member["profile"].get("status_text")
            )
        ]


class User:
    def __init__(
        self,
        slack_id: str,
        display_name: str,
        status_text: str,
        status_emoji: Optional[str] = None,
    ) -> None:
        self.slack_id: str = slack_id
        self.display_name: str = display_name
        self.status_text: str = status_text
        self.status_emoji: str = status_emoji or ""

    @property
    def in_the_office_probably(self) -> bool:
        return (
            bool(re.search(PATTERN, self.status_text, re.IGNORECASE))
            and not self.in_the_office_for_sure
        )

    @property
    def in_the_office_for_sure(self) -> bool:
        return bool(re.fullmatch(PATTERN, self.status_text, re.IGNORECASE))

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}"
            f'(slack_id="{self.slack_id}", '
            f'display_name="{self.display_name}", '
            f'status_text="{self.status_text}", '
            f'status_emoji="{self.status_emoji}")'
        )


class InTheOfficeMessageBuilder:
    def __init__(self, users: List[User]) -> None:
        self.users = self.filter_users_in_the_office(users)

    @staticmethod
    def filter_users_in_the_office(users: List[User]) -> List[User]:
        return [
            user
            for user in users
            if user.in_the_office_probably or user.in_the_office_for_sure
        ]

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(users={self.users})"

    @property
    def users_in_the_office_for_sure(self) -> List[User]:
        return [u for u in self.users if u.in_the_office_for_sure]

    @property
    def user_in_the_office_probably(self) -> List[User]:
        return [u for u in self.users if u.in_the_office_probably]

    def get_message(self) -> Dict[str, Any]:
        blocks = []
        if self.users_in_the_office_for_sure:
            blocks.append(self._get_message_block_users_in_the_office_for_sure())
        if self.user_in_the_office_probably:
            blocks.append(self._get_message_block_in_the_office_probably())

        return (
            {"blocks": blocks} if blocks else self._get_message_no_users_in_the_office()
        )

    def _get_message_no_users_in_the_office(
        self,
    ) -> Dict[str, List[Dict[str, Union[Dict, str]]]]:
        return {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "No one has 'In the office' status",
                    },
                }
            ]
        }

    def _get_message_block_users_in_the_office_for_sure(
        self,
    ) -> Dict[str, Union[str, Dict[str, str]]]:
        title = "In the office:"
        users_info = [
            f"• <@{u.slack_id}> {u.status_emoji} {u.status_text}"
            for u in self.users_in_the_office_for_sure
        ]
        info = "\n".join(users_info)
        return {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"{title}\n{info}"},
        }

    def _get_message_block_in_the_office_probably(
        self,
    ) -> Dict[str, Union[str, Dict[str, str]]]:
        title = "Maybe in the office:"
        users_info = [
            f"• <@{u.slack_id}> {u.status_emoji} {u.status_text}"
            for u in self.user_in_the_office_probably
        ]
        info = "\n".join(users_info)
        return {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"{title}\n{info}"},
        }


def slash(request) -> Union[Response, str]:
    if request.method == "POST" and request.form["token"] == SLACK_VERIFICATION_TOKEN:
        slack = SlackInfo()
        try:
            users_list = slack.get_users_list()
        except SlackApiError:
            message = (
                "Fetching users lists from Slack went wrong, "
                "try again little bit later."
            )
            logging.exception(message)
            return message
        message_builder = InTheOfficeMessageBuilder(users_list)
        payload = message_builder.get_message()
        return jsonify(payload)
