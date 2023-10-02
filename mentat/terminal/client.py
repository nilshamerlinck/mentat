import argparse
import asyncio
import glob
import logging
import signal
import traceback
from pathlib import Path
from typing import Any, Coroutine, List, Set

from prompt_toolkit.completion import Completer
from termcolor import cprint

from mentat.code_file import parse_intervals
from mentat.session import Session
from mentat.session_stream import StreamMessageSource
from mentat.terminal.output import print_stream_message
from mentat.terminal.prompt_completer import MentatCompleter
from mentat.terminal.prompt_session import MentatPromptSession

logger = logging.getLogger("mentat.terminal")
logger.setLevel(logging.INFO)


class TerminalClient:
    def __init__(
        self,
        paths: List[Path] = [],
        exclude_paths: List[Path] = [],
        no_code_map: bool = False,
        diff: str | None = None,
        pr_diff: str | None = None,
    ):
        self.paths = paths
        self.exclude_paths = exclude_paths
        self.no_code_map = no_code_map
        self.diff = diff
        self.pr_diff = pr_diff

        self.session: Session | None = None

        self._tasks: Set[asyncio.Task[None]] = set()
        self._should_exit = False
        self._force_exit = False

    def _create_task(self, coro: Coroutine[None, None, Any]):
        """Utility method for running a Task in the background"""

        def task_cleanup(task: asyncio.Task[None]):
            self._tasks.remove(task)

        task = asyncio.create_task(coro)
        task.add_done_callback(task_cleanup)
        self._tasks.add(task)

        return task

    async def _cprint_session_stream(self):
        assert isinstance(self.session, Session), "TerminalClient is not running"
        async for message in self.session.stream.listen():
            if self._should_exit:
                return
            print_stream_message(message)

    async def _handle_input_requests(self, prompt_completer: Completer | None = None):
        assert isinstance(self.session, Session), "TerminalClient is not running"
        while True:
            input_request_message = await self.session.stream.recv("input_request")
            # TODO: fix pyright typing for user_input
            user_input = await self._prompt_session.prompt_async(  # type: ignore
                completer=prompt_completer, handle_sigint=False
            )
            assert isinstance(user_input, str)
            if user_input == "q":
                self._should_exit = True
                return

            await self.session.stream.send(
                user_input,
                source=StreamMessageSource.CLIENT,
                channel=f"input_request:{input_request_message.id}",
            )

    async def _send_session_stream_interrupt(self):
        assert isinstance(self.session, Session), "TerminalClient is not running"
        await self.session.stream.send(
            "", source=StreamMessageSource.CLIENT, channel="interrupt"
        )

    def _handle_exit(self):
        assert isinstance(self.session, Session), "TerminalClient is not running"
        if (
            self.session.is_stopped
            or self.session.stream.interrupt_lock.locked() is False
        ):
            if self._should_exit:
                logger.debug("Force exiting client...")
                self._force_exit = True
            else:
                logger.debug("Should exit client...")
                self._should_exit = True

        else:
            logger.debug("Sending interrupt to session stream")
            self._create_task(self._send_session_stream_interrupt())

    def _init_signal_handlers(self):
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGINT, self._handle_exit)
        loop.add_signal_handler(signal.SIGTERM, self._handle_exit)

    async def _startup(self):
        assert self.session is None, "TerminalClient already running"

        logger.debug("Running startup")

        self.session = await Session.create(
            self.paths, self.exclude_paths, self.no_code_map, self.diff, self.pr_diff
        )
        self.session.start()
        self._prompt_session = MentatPromptSession(self.session)

        mentat_completer = MentatCompleter(self.session)

        self._create_task(mentat_completer.refresh_completions())
        self._create_task(self._cprint_session_stream())
        self._create_task(self._handle_input_requests(mentat_completer))

        logger.debug("Completed startup")

    async def _shutdown(self):
        assert isinstance(self.session, Session), "TerminalClient is not running"

        logger.debug("Running shutdown")

        # Stop all background tasks
        for task in self._tasks:
            task.cancel()
        logger.debug("Waiting for background tasks to finish. (CTRL+C to force quit)")
        while not self._force_exit:
            if all([task.cancelled() for task in self._tasks]):
                break
            await asyncio.sleep(0.01)

        # Stop session
        self.session.stop()
        while not self._force_exit and not self.session.is_stopped:
            await asyncio.sleep(0.01)
        self.session = None

        logger.debug("Completed shutdown")

    async def _main(self):
        assert isinstance(self.session, Session), "TerminalClient is not running"
        logger.debug("Running main loop")

        while not self._should_exit and not self.session.is_stopped:
            await asyncio.sleep(0.01)

    async def _run(self):
        try:
            self._init_signal_handlers()
            await self._startup()
            await self._main()
            await self._shutdown()
        # NOTE: if an exception is caught here, the main process will likely still run
        # due to background ascynio Tasks that are still running
        # NOTE: we should remove this try/except. The code inside of `self._run` should
        # never throw an exception
        except Exception as e:
            logger.error(f"Unexpected Exception {e}")
            logger.error(traceback.format_exc())

    def run(self):
        asyncio.run(self._run())


def expand_paths(paths: list[str]) -> list[Path]:
    globbed_paths = set[str]()
    invalid_paths = list[str]()
    for path in paths:
        new_paths = glob.glob(pathname=path, recursive=True)
        if new_paths:
            globbed_paths.update(new_paths)
        else:
            split = path.rsplit(":", 1)
            p = split[0]
            if len(split) > 1:
                # Parse additional syntax, e.g. "path/to/file.py:1-5,7,12-40"
                intervals = parse_intervals(split[1])
            else:
                intervals = None
            if Path(p).exists() and intervals:
                globbed_paths.add(path)
            else:
                invalid_paths.append(path)
    if invalid_paths:
        cprint("The following paths do not exist:", "light_yellow")
        print("\n".join(invalid_paths))
        exit()
    return [Path(path) for path in globbed_paths]


def run_cli():
    parser = argparse.ArgumentParser(
        description="Run conversation with command line args"
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=[],
        help="List of file paths, directory paths, or glob patterns",
    )
    parser.add_argument(
        "--exclude",
        "-e",
        nargs="*",
        default=[],
        help="List of file paths, directory paths, or glob patterns to exclude",
    )
    parser.add_argument(
        "--no-code-map",
        action="store_true",
        help="Exclude the file structure/syntax map from the system prompt",
    )
    parser.add_argument(
        "--diff",
        "-d",
        type=str,
        default=None,
        help="A git tree-ish (e.g. commit, branch, tag) to diff against",
    )
    parser.add_argument(
        "--pr-diff",
        "-p",
        type=str,
        default=None,
        help="A git tree-ish to diff against the latest common ancestor of",
    )
    args = parser.parse_args()
    paths = args.paths
    exclude_paths = args.exclude
    no_code_map = args.no_code_map
    diff = args.diff
    pr_diff = args.pr_diff

    # Expanding paths as soon as possible because some shells such as zsh automatically
    # expand globs and we want to avoid differences in functionality between shells
    terminal_client = TerminalClient(
        expand_paths(paths), expand_paths(exclude_paths), no_code_map, diff, pr_diff
    )
    terminal_client.run()