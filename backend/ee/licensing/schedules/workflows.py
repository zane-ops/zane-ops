from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from .activities import check_license
from zane_api.utils import Colors


@workflow.defn(name="check-license")
class CheckLicenseWorkflow:
    @workflow.run
    async def run(self, license_uuid: str) -> str:
        print(
            f"Running workflow {Colors.ORANGE}CheckLicenseWorkflow{Colors.ENDC} "
            f"with {Colors.GREY}{license_uuid=}{Colors.ENDC}"
        )
        retry_policy = RetryPolicy(
            maximum_attempts=5, maximum_interval=timedelta(seconds=30)
        )
        result = await workflow.execute_activity(
            check_license,
            license_uuid,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry_policy,
        )
        result_color = {
            "valid": Colors.GREEN,
            "removed": Colors.RED,
            "unreachable": Colors.YELLOW,
            "no_license": Colors.GREY,
        }.get(result, Colors.GREY)
        print(
            f"Workflow {Colors.ORANGE}CheckLicenseWorkflow{Colors.ENDC} "
            f"finished with result={result_color}{result}{Colors.ENDC} 🏁"
        )
        return result
