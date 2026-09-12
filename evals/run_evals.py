"""Run deterministic checks against the agent's final string output."""

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


EVALS_DIR = Path(__file__).resolve().parent
RESULTS_DIR = EVALS_DIR / "results"

# Direct script execution puts evals/ on sys.path; the agent lives one level up.
sys.path.insert(0, str(EVALS_DIR.parent))
from mcp_agent import run_agent


async def evaluate_case(case: dict) -> dict:
    result = {
        "id": case["id"],
        "prompt": case["prompt"],
        "passed": False,
        "output": "",
        "checks": [],
        "error": None,
    }

    try:
        agent_result = await run_agent(case["prompt"])
        if not isinstance(agent_result.final_output, str):
            raise TypeError("Expected run_agent().final_output to be a string")
        result["output"] = agent_result.final_output
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        print(f"  FAIL agent run: {result['error']}")

    output = result["output"].casefold()
    for check_type in ("must_contain", "must_not_contain"):
        for value in case.get(check_type, []):
            found = value.casefold() in output
            # An unavailable output cannot pass even a must_not_contain check.
            passed = result["error"] is None and (
                found if check_type == "must_contain" else not found
            )
            result["checks"].append(
                {"type": check_type, "value": value, "passed": passed}
            )
            status = "PASS" if passed else "FAIL"
            print(f"  {status} {check_type}: {value!r}")

    result["passed"] = result["error"] is None and all(
        check["passed"] for check in result["checks"]
    )
    return result


async def main() -> int:
    cases = json.loads((EVALS_DIR / "cases.json").read_text(encoding="utf-8"))
    timestamp = datetime.now(timezone.utc)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    case_results = []

    for case in cases:
        print(f"\nCase: {case['id']}")
        result = await evaluate_case(case)
        case_results.append(result)
        print(f"Case result: {'PASS' if result['passed'] else 'FAIL'}")

    checks = [check for result in case_results for check in result["checks"]]
    passed = sum(check["passed"] for check in checks)
    summary = {"passed": passed, "failed": len(checks) - passed, "total": len(checks)}
    report = {
        "timestamp": timestamp.isoformat(),
        "summary": summary,
        "cases": case_results,
    }
    # Include microseconds so runs started in the same second have separate files.
    result_path = RESULTS_DIR / f"{timestamp:%Y-%m-%d_%H%M%S_%f}.json"
    with result_path.open("x", encoding="utf-8") as result_file:
        json.dump(report, result_file, indent=2, ensure_ascii=False)
        result_file.write("\n")

    print(f"\nPassed checks: {summary['passed']}")
    print(f"Failed checks: {summary['failed']}")
    print(f"Total checks: {summary['total']}")
    print(f"Results saved to: {result_path}")
    return 0 if all(result["passed"] for result in case_results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
