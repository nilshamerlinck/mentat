import asyncio
import logging
import signal
import sys
from typing import Iterable, Set

from ipdb import set_trace

from mentat.llm_api import CostTracker

from .config_manager import ConfigManager
from .git_handler import get_shared_git_root_for_paths
from .rpc import RpcServer
from .session import Session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mentat.engine")


class Engine:
    """Manages all processes."""

    def __init__(self, with_rpc_server: bool = False):
        self.rpc_server = RpcServer() if with_rpc_server else None
        self.sessions: Set[Session] = set()

        self._should_exit = False
        self._force_exit = False
        self._tasks: Set[asyncio.Task] = set()

    ### rpc-exposed methods (terminal client can call these directly)

    async def on_connect(self):
        """Sets up an RPC connection with a client"""
        ...

    async def disconnect(self):
        """Closes an RPC connection with a client"""
        ...

    async def restart(self):
        """Restart the MentatEngine and RPC server"""
        ...

    async def shutdown(self):
        """Shutdown the MentatEngine and RPC server"""
        ...

    # Conversation

    async def create_session(
        self,
        paths: Iterable[str],
        exclude_paths: Iterable[str] | None,
        no_code_map: bool,
    ):
        session = Session()
        session.start(paths, exclude_paths, CostTracker(), no_code_map)
        self.sessions.add(session)

        return session

    async def create_conversation_message(self):
        ...

    async def get_conversation_cost(self):
        ...

    # Completions

    async def get_conversation_completions(self):
        ...

    # Commands

    async def get_commands(self):
        ...

    async def run_command(self):
        ...

    ### lifecycle methods

    async def heartbeat(self):
        while True:
            logger.debug("heartbeat")
            await asyncio.sleep(3)

    def _handle_exit(self):
        print("got a signal")
        if self._should_exit:
            self._force_exit = True
        else:
            self._should_exit = True

    def _init_signal_handlers(self):
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGINT, self._handle_exit)
        loop.add_signal_handler(signal.SIGTERM, self._handle_exit)

    async def _startup(self):
        logger.debug("Starting Engine...")
        heahtheck_task = asyncio.create_task(self.heartbeat())
        self._tasks.add(heahtheck_task)

    async def _main_loop(self):
        logger.debug("Running Engine...")

        counter = 0
        while not self._should_exit:
            counter += 1
            counter = counter % 86400
            await asyncio.sleep(0.1)

    async def _shutdown(self):
        logger.debug("Shutting Engine down...")

        for task in self._tasks:
            task.cancel()
        logger.debug("Waiting for Jobs to finish. (CTRL+C to force quit)")
        while not self._force_exit:
            if all([task.cancelled() for task in self._tasks]):
                break
            await asyncio.sleep(0.1)

        if self._force_exit:
            logger.debug("Force exiting.")

        logger.debug("Engine has stopped")

    async def _run(self, install_signal_handlers: bool = True):
        if install_signal_handlers:
            self._init_signal_handlers()
        await self._startup()
        await self._main_loop()
        await self._shutdown()

    def run(self, install_signal_handlers: bool = True):
        asyncio.run(self._run(install_signal_handlers=install_signal_handlers))


def run_cli():
    mentat_engine = Engine()
    mentat_engine.run()
