from typing import Any

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from reic.modules.scenarios.application.dto import RiskInput, SimulateInput
from reic.modules.scenarios.domain.errors import ScenarioValidationError
from reic.modules.scenarios.domain.risk import LEVELS, summarize_risks
from reic.modules.scenarios.domain.simulation import simulate


def _validate[M: BaseModel](model: type[M], data: dict[str, Any]) -> M:
    try:
        return model.model_validate(data)
    except PydanticValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc']) or 'body'}: {e['msg']}" for e in exc.errors()
        )
        raise ScenarioValidationError(problems) from exc


class ScenarioService:
    def simulate(self, data: dict[str, Any]) -> dict[str, Any]:
        return simulate(_validate(SimulateInput, data).to_params())

    def risk_summary(self, data: dict[str, Any]) -> dict[str, Any]:
        items = summarize_risks(_validate(RiskInput, data).to_inputs())
        overall = max((i["level"] for i in items), key=LEVELS.index)
        return {"overall": overall, "items": items}
