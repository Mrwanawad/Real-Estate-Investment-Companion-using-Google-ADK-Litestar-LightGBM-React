from collections.abc import Callable
from typing import Any

from litestar import Controller, post
from litestar.exceptions import ValidationException
from litestar.params import JSONBody
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from reic.modules.financing.application.dto import (
    CompareFinancingInput,
    InstallmentScheduleInput,
    MortgageScheduleInput,
)
from reic.modules.financing.application.use_cases import (
    BuildInstallmentSchedule,
    BuildMortgageSchedule,
    CompareFinancingOptions,
)
from reic.modules.financing.domain.errors import FinancingValidationError


def _run[M: BaseModel](
    model: type[M], data: Any, execute: Callable[[M], dict[str, Any]]
) -> dict[str, Any]:
    """Validate the body and run the use case; any input problem becomes a 400."""
    try:
        return execute(model.model_validate(data))
    except PydanticValidationError as exc:
        problems = [
            {"field": ".".join(str(part) for part in err["loc"]), "message": err["msg"]}
            for err in exc.errors()
        ]
        raise ValidationException(detail="Invalid request body", extra=problems) from exc
    except FinancingValidationError as exc:
        raise ValidationException(detail=str(exc)) from exc


class FinancingController(Controller):
    path = "/financing"

    @post("/installments", status_code=200, sync_to_thread=False)
    def installments(self, data: JSONBody[dict[str, Any]]) -> dict[str, Any]:
        return _run(InstallmentScheduleInput, data, BuildInstallmentSchedule().execute)

    @post("/mortgage", status_code=200, sync_to_thread=False)
    def mortgage(self, data: JSONBody[dict[str, Any]]) -> dict[str, Any]:
        return _run(MortgageScheduleInput, data, BuildMortgageSchedule().execute)

    @post("/compare", status_code=200, sync_to_thread=False)
    def compare(self, data: JSONBody[dict[str, Any]]) -> dict[str, Any]:
        return _run(CompareFinancingInput, data, CompareFinancingOptions().execute)
