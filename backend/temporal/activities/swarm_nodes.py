import asyncio
from datetime import timedelta
import shlex
import shutil
from time import monotonic
from typing import Any, Dict, List, cast
from temporalio import activity, workflow
import tempfile
from temporalio.exceptions import ApplicationError
import os
import os.path


with workflow.unsafe.imports_passed_through():
    pass


from ..shared import SwarmNodeDetails


class SwarmNodeActivities:
    @activity.defn
    async def prepare(self, node: SwarmNodeDetails):
        pass
