import subprocess
from pathlib import Path

import pytest

from mentat.code_context import CodeContext
from mentat.commands import (
    AddCommand,
    Command,
    HelpCommand,
    InvalidCommand,
    RemoveCommand,
)


def test_invalid_command():
    assert isinstance(Command.create_command("non-existent"), InvalidCommand)


@pytest.mark.asyncio
async def test_help_command():
    command = Command.create_command("help")
    await command.apply()
    assert isinstance(command, HelpCommand)


@pytest.mark.asyncio
async def test_commit_command(temp_testbed):
    file_name = "test_file.py"
    with open(file_name, "w") as f:
        f.write("# Commit me!")

    command = Command.create_command("commit")
    await command.apply("commit", "test_file committed")
    assert subprocess.check_output(["git", "diff", "--name-only"], text=True) == ""


@pytest.mark.asyncio
async def test_add_command(mock_config):
    code_context = await CodeContext.create(
        config=mock_config,
        paths=[],
        exclude_paths=[],
    )
    command = Command.create_command("add", code_context=code_context)
    assert isinstance(command, AddCommand)
    await command.apply("__init__.py")
    assert Path("__init__.py") in code_context.files


@pytest.mark.asyncio
async def test_remove_command(mock_config):
    code_context = await CodeContext.create(
        config=mock_config,
        paths=["__init__.py"],
        exclude_paths=[],
    )
    command = Command.create_command("remove", code_context=code_context)
    assert isinstance(command, RemoveCommand)
    await command.apply("__init__.py")
    assert Path("__init__.py") not in code_context.files
