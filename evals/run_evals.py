"""Run deterministic checks against the agent's final output and tool calls."""

import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path


EVALS_DIR = Path(__file__).resolve().parent
RESULTS_DIR = EVALS_DIR / "results"
TRIALS_PER_CASE = 5

MULTIPLIERS = {
    "k": Decimal("1000"),
    "thousand": Decimal("1000"),
    "m": Decimal("1000000"),
    "million": Decimal("1000000"),
    "b": Decimal("1000000000"),
    "billion": Decimal("1000000000"),
}
AMOUNT_PATTERN = re.compile(
    r"""
    (?<![\w.,$+-])
    (?P<sign>[+-]?)(?=\$|[0-9]|\.)\$?\s*
    (?P<number>
        (?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?
        |\.[0-9]+
    )
    (?:\s*(?P<suffix>thousand|million|billion|[kmb]))?
    (?!\w|[.,][0-9]|-[0-9])
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Direct script execution puts evals/ on sys.path; the agent lives one level up.
sys.path.insert(0, str(EVALS_DIR.parent))
from agents.items import ToolCallItem

from mcp_agent import run_agent


def extract_amounts(output: str) -> set[Decimal]:
    """Normalize numeric amounts, without matching fragments of larger numbers."""
    amounts = set()
    for match in AMOUNT_PATTERN.finditer(output):
        number = Decimal(match["sign"] + match["number"].replace(",", ""))
        suffix = (match["suffix"] or "").lower()
        amounts.add(number * MULTIPLIERS.get(suffix, Decimal("1")))
    return amounts


async def evaluate_case(case: dict) -> dict:
    result = {
        "id": case["id"],
        "prompt": case["prompt"],
        "passed": False,
        "output": "",
        "tools_called": [],
        "checks": [],
        "error": None,
    }

    try:
        agent_result = await run_agent(case["prompt"])
        if not isinstance(agent_result.final_output, str):
            raise TypeError("Expected run_agent().final_output to be a string")
        result["output"] = agent_result.final_output
        # Inspect SDK call records, not tool names mentioned in the final answer.
        # Preserve call order and repeated calls in the saved report.
        result["tools_called"] = [
            item.tool_name
            for item in agent_result.new_items
            if isinstance(item, ToolCallItem) and item.tool_name is not None
        ]
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        print(f"  FAIL agent run: {result['error']}")

    tools_display = (
        "unavailable" if result["error"] else ", ".join(result["tools_called"]) or "none"
    )
    print(f"  Tools called: {tools_display}")
    output = result["output"].casefold()
    for check_type in (
        "must_contain", "must_not_contain", "required_tools", "forbidden_tools"
    ):
        for value in case.get(check_type, []):
            if check_type in ("required_tools", "forbidden_tools"):
                # Tool identifiers are exact, case-sensitive names.
                found = value in result["tools_called"]
            else:
                found = value.casefold() in output
            # A failed run cannot pass absence checks on unavailable results.
            passed = result["error"] is None and (
                found if check_type in ("must_contain", "required_tools") else not found
            )
            result["checks"].append(
                {"type": check_type, "value": value, "passed": passed}
            )
            status = "PASS" if passed else "FAIL"
            print(f"  {status} {check_type}: {value!r}")

    amounts = extract_amounts(result["output"])
    for value in case.get("must_contain_amounts", []):
        passed = result["error"] is None and Decimal(str(value)) in amounts
        result["checks"].append(
            {"type": "must_contain_amount", "value": value, "passed": passed}
        )
        status = "PASS" if passed else "FAIL"
        print(f"  {status} must_contain_amount: {value!r}")

    result["passed"] = result["error"] is None and all(
        check["passed"] for check in result["checks"]
    )
    return result


async def main() -> int:
    if type(TRIALS_PER_CASE) is not int or TRIALS_PER_CASE < 1:
        print("TRIALS_PER_CASE must be a positive integer.")
        return 1

    cases = json.loads((EVALS_DIR / "cases.json").read_text(encoding="utf-8"))
    timestamp = datetime.now(timezone.utc)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    case_results = []

    for case in cases:
        print(f"\nCase: {case['id']}")
        trials = []
        for trial_number in range(1, TRIALS_PER_CASE + 1):
            print(f"\nTrial {trial_number}/{TRIALS_PER_CASE}")
            result = await evaluate_case(case)
            result["trial"] = trial_number
            trials.append(result)
            print(
                f"Trial {trial_number}/{TRIALS_PER_CASE}: "
                f"{'PASS' if result['passed'] else 'FAIL'}"
            )

        passed_trials = sum(trial["passed"] for trial in trials)
        total_trials = len(trials)
        case_summary = {
            "passed_trials": passed_trials,
            "failed_trials": total_trials - passed_trials,
            "total_trials": total_trials,
            "pass_rate": passed_trials / total_trials,
        }
        case_results.append({
            "id": case["id"],
            "prompt": case["prompt"],
            "passed": passed_trials == total_trials,
            "summary": case_summary,
            "trials": trials,
        })
        print(
            f"\nCase pass rate: {passed_trials}/{total_trials} "
            f"({case_summary['pass_rate']:.1%})"
        )

    all_trials = [trial for case in case_results for trial in case["trials"]]
    checks = [check for trial in all_trials for check in trial["checks"]]
    passed = sum(check["passed"] for check in checks)
    passed_trials = sum(trial["passed"] for trial in all_trials)
    total_trials = len(all_trials)
    summary = {
        "passed": passed,
        "failed": len(checks) - passed,
        "total": len(checks),
        "passed_trials": passed_trials,
        "failed_trials": total_trials - passed_trials,
        "total_trials": total_trials,
        "trial_pass_rate": passed_trials / total_trials if total_trials else 0.0,
    }
    report = {
        "timestamp": timestamp.isoformat(),
        "trials_per_case": TRIALS_PER_CASE,
        "summary": summary,
        "cases": case_results,
    }
    # Include microseconds so runs started in the same second have separate files.
    result_path = RESULTS_DIR / f"{timestamp:%Y-%m-%d_%H%M%S_%f}.json"
    with result_path.open("x", encoding="utf-8") as result_file:
        json.dump(report, result_file, indent=2, ensure_ascii=False)
        result_file.write("\n")

    print(f"\nPassed trials: {summary['passed_trials']}")
    print(f"Failed trials: {summary['failed_trials']}")
    print(f"Total trials: {summary['total_trials']}")
    print(f"Trial pass rate: {summary['trial_pass_rate']:.1%}")
    print(f"\nPassed checks: {summary['passed']}")
    print(f"Failed checks: {summary['failed']}")
    print(f"Total checks: {summary['total']}")
    print(f"Results saved to: {result_path}")
    return 0 if all(result["passed"] for result in case_results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
