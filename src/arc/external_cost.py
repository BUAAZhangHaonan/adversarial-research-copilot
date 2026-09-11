"""Validate service usage estimates without confusing them with provider invoices."""
from decimal import Decimal, InvalidOperation


def service_cost(value):
    if not isinstance(value, dict) or value.get("schema_version") != "mcp.cost.v1":
        return None
    if value.get("currency") != "CNY" or value.get("scope") != "provider_api_only":
        return None
    if type(value.get("complete")) is not bool:
        return None
    try:
        lower = Decimal(str(value.get("lower_cny")))
        upper = None if value.get("upper_cny") is None else Decimal(str(value["upper_cny"]))
        if not lower.is_finite() or lower < 0 or (upper is not None and (not upper.is_finite() or upper < lower)):
            return None
        if value["complete"] and upper is None:
            return None
        total = value.get("total_cny")
        if total is not None and (upper is None or Decimal(str(total)) != lower or lower != upper):
            return None
        for key in ("model_calls", "unknown_calls"):
            if type(value.get(key)) is not int or value[key] < 0:
                return None
        if value["unknown_calls"] > value["model_calls"] or (value["complete"] and value["unknown_calls"]):
            return None
        if value.get("basis") not in {"no_paid_calls", "estimated_usage", "partial_usage", "unmetered"}:
            return None
        if value.get("basis") == "no_paid_calls" and (lower != 0 or upper != 0 or value["model_calls"]):
            return None
    except (InvalidOperation, ValueError, TypeError):
        return None
    return dict(value)


def cost_for_model(result):
    """Full attempts remain in tool traces; models only need the compact totals."""
    cost = result.get("cost")
    if not isinstance(cost, dict):
        return result
    return {**result, "cost": {key: cost.get(key) for key in (
        "currency", "basis", "total_cny", "lower_cny", "upper_cny", "complete",
        "model_calls", "unknown_calls", "reused_result")}}
