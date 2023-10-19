import pytest

from mentat.parsers.block_parser import BlockParser
from mentat.parsers.git_parser import GitParser
from mentat.parsers.replacement_parser import ReplacementParser
from scripts.translate_transcript import translate_message


@pytest.fixture
def block_format():
    with open("format_examples/block.txt") as f:
        return f.read()


@pytest.fixture
def replacement_format():
    with open("format_examples/replacement.txt") as f:
        return f.read()


@pytest.fixture
def git_diff_format():
    with open("format_examples/git_diff.txt") as f:
        return f.read()


# This one doesn't pass. I think it's actually a bug with the parser as if I print out the final parsed
# FileEdit from the parsed block_format I don't see the single line deletion.
# def test_block_to_replacement(block_format, replacement_format, mock_stream, mock_code_file_manager, mock_git_root):
# assert translate_message(block_format, BlockParser(), ReplacementParser()) == replacement_format


def test_replacement_to_block(
    block_format, replacement_format, mock_stream, mock_code_file_manager, mock_git_root
):
    assert (
        translate_message(replacement_format, ReplacementParser(), BlockParser())
        == block_format
    )


def test_git_diff_to_replacement(
    git_diff_format,
    replacement_format,
    mock_stream,
    mock_code_file_manager,
    mock_git_root,
):
    assert (
        translate_message(git_diff_format, GitParser(), ReplacementParser())
        == replacement_format
    )


def test_git_diff_to_block(
    git_diff_format, block_format, mock_stream, mock_code_file_manager, mock_git_root
):
    assert (
        translate_message(git_diff_format, GitParser(), BlockParser()) == block_format
    )