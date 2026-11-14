"""E029. One authored press deadline, two possible targets of the same notice.

Only source A supplies the scheduled supporter row. A and C are different
occurrences by P; C supplies no fallback basis for the A row (or vice versa).
There is a separate standing basis for one closed preservation copy. A plate
is a snapshot for one issue. No readers, distribution or harms are modeled.
"""
from dataclasses import asdict, dataclass, replace
import json


NAMED = "service_info_and_P_as_current_supporter_from_A"
COVERED = "service_info_only"


@dataclass(frozen=True)
class Desk:
    lobby: str = NAMED
    locked_issue: str | None = None
    closed_copy_made: bool = False


@dataclass(frozen=True)
class Handling:
    cover_name: bool
    make_closed_copy: bool


POLICIES = {
    "stop_all": Handling(True, False),
    "continue_all": Handling(False, True),
    "by_use": Handling(True, True),
}
ORDERS = {
    "handle_then_press": ("handle", "press"),
    "press_then_handle": ("press", "handle"),
}


def run(policy: Handling, events: tuple[str, str]) -> Desk:
    # The notice has already arrived; its target is unavailable to the desk.
    desk = Desk()
    for event in events:
        if event == "handle":
            desk = replace(desk, lobby=COVERED if policy.cover_name else desk.lobby,
                           closed_copy_made=policy.make_closed_copy)
        elif event == "press":
            if desk.locked_issue is not None:
                raise ValueError("Only one issue may lock")
            desk = replace(desk, locked_issue=desk.lobby)
        else:
            raise ValueError(event)
    return desk


def assess(locked_issue: str, hidden_target: str) -> dict:
    # Author's hindsight. In world C the scheduled A row retains its old basis.
    # These are two edition-level counts, not a verdict about P's current views.
    return {
        "withdrawn_A_attribution_printed": int(hidden_target == "A" and locked_issue == NAMED),
        "unaffected_A_print_opportunity_forgone": int(hidden_target == "C" and locked_issue == COVERED),
    }


def check(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)


def main() -> None:
    # Oracle tuples: final lobby, locked issue, private copy, (world A count,
    # world C count). The off-diagonal counter in each world must always be 0.
    oracle = {
        ("handle_then_press", "stop_all"): (COVERED, COVERED, False, (0, 1)),
        ("handle_then_press", "continue_all"): (NAMED, NAMED, True, (1, 0)),
        ("handle_then_press", "by_use"): (COVERED, COVERED, True, (0, 1)),
        ("press_then_handle", "stop_all"): (COVERED, NAMED, False, (1, 0)),
        ("press_then_handle", "continue_all"): (NAMED, NAMED, True, (1, 0)),
        ("press_then_handle", "by_use"): (COVERED, NAMED, True, (1, 0)),
    }
    cases = []
    for order, events in ORDERS.items():
        for name, policy in POLICIES.items():
            desk = run(policy, events)
            lobby, issue, made_copy, (in_a, in_c) = oracle[order, name]
            check(desk == Desk(lobby, issue, made_copy), f"{order}/{name}: operations")
            check(desk.locked_issue is not None, "missing issue")
            # Both worlds have exactly this desk output. Only the assessor sees
            # the target, after the edition has locked.
            worlds = {target: assess(desk.locked_issue, target) for target in ("A", "C")}
            for target, expected in (("A", (in_a, 0)), ("C", (0, in_c))):
                observed = worlds[target]
                check((observed["withdrawn_A_attribution_printed"],
                       observed["unaffected_A_print_opportunity_forgone"]) == expected,
                      f"{order}/{name}/{target}: hindsight")
            for later_lobby in (NAMED, COVERED):
                check(replace(desk, lobby=later_lobby).locked_issue == issue, "plate changed")
            cases.append({"order": order, "policy": name, "desk": asdict(desk), "worlds": worlds})

    print(json.dumps({
        "model": "E029-authored-press-deadline",
        "fixed_for_all_cases": {
            "archived_occurrences": ["A", "C"],
            "originals": "retained_unchanged",
            "notice": "received_target_unresolved",
            "exhibition": "undecided",
            "deadline": 9,
        },
        "cases": cases,
    }, indent=2))


if __name__ == "__main__":
    main()
