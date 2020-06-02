import os
from typing import Dict, Union

import mock
import pytest

os.environ["SLACK_API_TOKEN"] = "SLACK_API_TOKEN"
os.environ["SLACK_VERIFICATION_TOKEN"] = "SLACK_VERIFICATION_TOKEN"

import main  # noqa isort:skip


def get_single_member_data(
    is_bot: bool = False,
    deleted: bool = False,
    id: str = "A1",
    display_name: str = "display_name_test",
    status_text: str = "status_text_test",
    status_emoji: str = ":)",
) -> Dict[str, Union[str, Dict[str, str]]]:
    return {
        "is_bot": is_bot,
        "deleted": deleted,
        "id": id,
        "profile": {
            "display_name": display_name,
            "status_text": status_text,
            "status_emoji": status_emoji,
        },
    }


@mock.patch("slack.web.base_client.BaseClient.api_call")
class TestSlackInfo:
    def test_basic_get_users_list(self, api_call):
        main.SlackInfo().get_users_list()
        api_call.assert_called_once_with("users.list", http_verb="GET", params={})

    def test_basic_good_get_list(self, api_call):
        api_call.return_value.data = {"members": [get_single_member_data()]}
        response = main.SlackInfo().get_users_list()

        assert len(response) == 1
        assert isinstance(response[0], main.User)

    @pytest.mark.parametrize(
        "single_member_data",
        [
            get_single_member_data(is_bot=True),
            get_single_member_data(deleted=True),
            get_single_member_data(status_text=""),
            get_single_member_data(status_text=None),
        ],
    )
    def test_basic_empty_get_list(self, api_call, single_member_data):
        api_call.return_value.data = {"members": [single_member_data]}
        response = main.SlackInfo().get_users_list()
        assert len(response) == 0


class TestUser:
    def test_user_in_the_office_for_sure(self):
        user = main.User(
            slack_id="A1", display_name="display_name", status_text="In the office"
        )
        assert user.in_the_office_for_sure
        assert not user.in_the_office_probably

    @pytest.mark.parametrize(
        "status_text", [" ", "In home", "something"],
    )
    def test_user_not_in_the_office(self, status_text):
        user = main.User(
            slack_id="A1", display_name="display_name", status_text=status_text
        )
        assert not user.in_the_office_for_sure
        assert not user.in_the_office_probably

    @pytest.mark.parametrize(
        "status_text", ["maybe in the office", "maybe not in the office"],
    )
    def test_user_not_in_the_office_probably(self, status_text):
        user = main.User(
            slack_id="A1", display_name="display_name", status_text=status_text
        )
        assert not user.in_the_office_for_sure
        assert user.in_the_office_probably


class TestInTheOfficeMessageBuilder:
    def test_no_users_in_the_office(self):
        users_list = [
            main.User(
                slack_id="A1", display_name="display_name", status_text="something"
            ),
            main.User(slack_id="A2", display_name="display_name", status_text=""),
            main.User(slack_id="A3", display_name="display_name", status_text="blah"),
        ]
        message_builder = main.InTheOfficeMessageBuilder(users_list)
        payload = message_builder.get_message()
        assert len(payload["blocks"]) == 1
        assert (
            payload["blocks"][0]["text"]["text"] == "No one has 'In the office' status"
        )

    def test_users_in_the_office(self):
        users_list = [
            main.User(
                slack_id="A1",
                display_name="display_name",
                status_text="In the office",
                status_emoji=":office:",
            ),
            main.User(
                slack_id="A2",
                display_name="display_name",
                status_text="maybe in the office",
                status_emoji=":?",
            ),
            main.User(slack_id="A3", display_name="display_name", status_text="blah"),
        ]
        message_builder = main.InTheOfficeMessageBuilder(users_list)
        payload = message_builder.get_message()
        assert len(payload["blocks"]) == 2
        assert (
            payload["blocks"][0]["text"]["text"]
            == "In the office:\n• <@A1> :office: In the office"
        )
        assert (
            payload["blocks"][1]["text"]["text"]
            == "Maybe in the office:\n• <@A2> :? maybe in the office"
        )
