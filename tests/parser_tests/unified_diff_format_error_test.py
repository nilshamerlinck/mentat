from pathlib import Path
from textwrap import dedent

from mentat.app import run
from tests.conftest import ConfigManager, pytest


@pytest.fixture(autouse=True)
def unified_diff_parser(mocker):
    mock_method = mocker.MagicMock()
    mocker.patch.object(ConfigManager, "parser", new=mock_method)
    mock_method.return_value = "unified-diff"


def test_not_matching(mock_call_llm_api, mock_collect_user_input, mock_setup_api_key):
    temp_file_name = Path("temp.py")
    with open(temp_file_name, "w") as f:
        f.write(dedent("""\
            # This is
            # a temporary file
            # with
            # 4 lines"""))

    mock_collect_user_input.side_effect = [
        "",
        "y",
        KeyboardInterrupt,
    ]
    mock_call_llm_api.set_generator_values([dedent(f"""\
        Conversation

        --- {temp_file_name}
        +++ {temp_file_name}
         # Not matching
        -# a temporary file
        -# with
        +# your captain speaking
         # 4 lines""")])

    run([temp_file_name])
    with open(temp_file_name, "r") as f:
        content = f.read()
        expected_content = dedent("""\
            # This is
            # a temporary file
            # with
            # 4 lines""")
    assert content == expected_content


def test_no_prefix(mock_call_llm_api, mock_collect_user_input, mock_setup_api_key):
    temp_file_name = Path("temp.py")
    with open(temp_file_name, "w") as f:
        f.write(dedent("""\
            # This is
            # a temporary file
            # with
            # 4 lines"""))

    mock_collect_user_input.side_effect = [
        "",
        "y",
        KeyboardInterrupt,
    ]
    mock_call_llm_api.set_generator_values([dedent(f"""\
        Conversation

        --- {temp_file_name}
        +++ {temp_file_name}
        # This is
        -# a temporary file
        -# with
        +# your captain speaking
        # 4 lines""")])

    run([temp_file_name])
    with open(temp_file_name, "r") as f:
        content = f.read()
        expected_content = dedent("""\
            # This is
            # a temporary file
            # with
            # 4 lines""")
    assert content == expected_content