"""E026: scoped withdrawal and partial delivery in an authored fictional model.

Python 3.10+, standard library only. No network access or file mutation.
Event identity, scope and ordering are stipulated, not authenticated by this code.
"""
from dataclasses import dataclass, replace
from itertools import product
import json


TARGET = "V1"
SCOPES = {"pause_request", "name_permission", "preserve_request"}
SOURCE = ("V1", 2, "Please pause the exhibit; preserve the reading.")


@dataclass(frozen=True)
class Event:
    eid: str
    revision: int
    issued: int
    target: str
    changes: tuple[tuple[str, bool], ...]


@dataclass(frozen=True)
class Replica:
    name: str
    received: tuple[tuple[str, int], ...]
    applied: tuple[tuple[str, int], ...]


BASE = Event("G1", 1, 2, TARGET, (
    ("pause_request", True), ("name_permission", True),
    ("preserve_request", True)))


def require(value: bool, label: str) -> None:
    if not value:
        raise AssertionError(label)


def withdrawal(scopes: tuple[str, ...]) -> Event:
    return Event("W2", 2, 4, TARGET, tuple((s, False) for s in scopes))


def validate(events: tuple[Event, ...], replica: Replica) -> dict[str, Event]:
    ids, revisions = set(), set()
    for event in events:
        if event.eid in ids or event.revision in revisions:
            raise ValueError("duplicate event identity or revision")
        if event.target != TARGET or event.revision < 1 or event.issued < 0:
            raise ValueError("invalid target or event coordinates")
        fields = [s for s, _ in event.changes]
        if not fields or len(fields) != len(set(fields)):
            raise ValueError("empty or duplicate scope")
        if any(s not in SCOPES or type(v) is not bool for s, v in event.changes):
            raise ValueError("unknown scope or non-boolean value")
        ids.add(event.eid)
        revisions.add(event.revision)
    ordered = sorted(events, key=lambda e: e.revision)
    if not ordered or ordered[0] != BASE:
        raise ValueError("missing baseline")
    if any(a.issued > b.issued for a, b in zip(ordered, ordered[1:])):
        raise ValueError("revision time goes backwards")
    if len(ordered) != 2 or ordered[1].eid != "W2" or ordered[1].revision != 2:
        raise ValueError("this model requires one grant and one withdrawal")
    if any(s not in {"pause_request", "name_permission"} or value is not False
           for s, value in ordered[1].changes):
        raise ValueError("later re-endorsement is outside this model")
    by_id = {e.eid: e for e in events}
    for eid, received_at in replica.received:
        if eid not in by_id or received_at < by_id[eid].issued:
            raise ValueError("unknown or prematurely received event")
    for eid, applied_at in replica.applied:
        if eid not in by_id or not any(
                rid == eid and at <= applied_at for rid, at in replica.received):
            raise ValueError("application without prior receipt")
    return by_id


def project(events: tuple[Event, ...], replica: Replica, now: int) -> dict:
    by_id = validate(events, replica)
    received = {eid for eid, at in replica.received if at <= now}
    applied = {eid for eid, at in replica.applied if at <= now}
    if BASE.eid not in applied:
        raise ValueError("query precedes local baseline")
    fields, times = {}, {}
    for event in sorted((by_id[i] for i in applied), key=lambda e: e.revision):
        for scope, value in event.changes:
            fields[scope], times[scope] = value, event.issued
    # Receipt is not rendering. A pending withdrawal nevertheless blocks new reuse.
    known_block = any(not value and scope in {"pause_request", "name_permission"}
                      for eid in received for scope, value in by_id[eid].changes)
    return {
        "local_as_of_values": fields,
        "scope_event_times": times,
        "pending_events": sorted(received - applied),
        "historical_V1": "preserved_as_dated_record",
        "current_position": "not_certified_from_local_cache",
        "new_named_support_use": ("blocked_by_known_withdrawal" if known_block
                                  else "requires_current_confirmation"),
        "external_claim_truth": "not_assessed",
    }


def make_replica(name: str, level: int) -> Replica:
    if level not in (0, 1, 2):
        raise ValueError("invalid delivery level")
    return Replica(name, (("G1", 2),) + ((("W2", 4),) if level else ()),
                   (("G1", 2),) + ((("W2", 5),) if level == 2 else ()))


def coverage(events: tuple[Event, ...], replicas: tuple[Replica, ...], now: int) -> dict:
    if not replicas or len({r.name for r in replicas}) != len(replicas):
        raise ValueError("empty registry or duplicate replica")
    for replica in replicas:
        project(events, replica, now)
    received = [r.name for r in replicas if ("W2" in
                {eid for eid, at in r.received if at <= now})]
    applied = [r.name for r in replicas if ("W2" in
               {eid for eid, at in r.applied if at <= now})]
    return {
        "registered": len(replicas), "received": len(received),
        "applied": len(applied),
        "unapplied": sorted(r.name for r in replicas if r.name not in applied),
        "complete_within_registry": len(applied) == len(replicas),
        "global_completion": "not_certified",
    }


def main() -> None:
    both = withdrawal(("pause_request", "name_permission"))
    events = (BASE, both)
    original = (events, SOURCE)
    named = {label: project(events, make_replica("copy", level), 6)
             for label, level in (("unreceived", 0), ("received_not_applied", 1),
                                  ("applied", 2))}
    named["before_withdrawal"] = project(events, make_replica("copy", 2), 3)
    for label, scope in (("request_only", "pause_request"),
                         ("permission_only", "name_permission")):
        value = project((BASE, withdrawal((scope,))), make_replica("copy", 2), 6)
        require(value["local_as_of_values"][scope] is False, label)
        other = "name_permission" if scope == "pause_request" else "pause_request"
        require(value["local_as_of_values"][other] is True, "no scope spill")
        named[label] = value
    require(named["received_not_applied"]["local_as_of_values"]["pause_request"],
            "receipt must not silently rewrite the rendered copy")
    require(named["received_not_applied"]["new_named_support_use"] ==
            "blocked_by_known_withdrawal", "pending notice blocks new reuse")
    require(named["before_withdrawal"] == named["unreceived"], "no future leak")

    # Delivery order and duplicates cannot resurrect an old grant in this model.
    late = Replica("copy", (("W2", 4), ("G1", 6), ("G1", 6)),
                   (("W2", 5), ("G1", 6), ("G1", 6)))
    require(project(events, late, 6) == named["applied"], "late grant resurrected")
    require(project(tuple(reversed(events)), late, 6) == named["applied"],
            "event input order mattered")

    configurations = views = 0
    for scopes in (("pause_request",), ("name_permission",),
                   ("pause_request", "name_permission")):
        ledger = (BASE, withdrawal(scopes))
        for levels in product((0, 1, 2), repeat=4):
            configurations += 1
            replicas = tuple(make_replica(f"D{i + 1}", level)
                             for i, level in enumerate(levels))
            report = coverage(ledger, replicas, 6)
            require(report["received"] == sum(v > 0 for v in levels), "receipts")
            require(report["applied"] == levels.count(2), "applications")
            require(report["complete_within_registry"] == all(v == 2 for v in levels),
                    "receipt counted as completion")
            for replica, level in zip(replicas, levels):
                views += 1
                result = project(ledger, replica, 6)
                for scope in SCOPES:
                    expected = not (level == 2 and scope in scopes)
                    require(result["local_as_of_values"][scope] == expected, scope)
                    expected_time = 4 if level == 2 and scope in scopes else 2
                    require(result["scope_event_times"][scope] == expected_time, "scope time")
                require(result == project(ledger, replace(replica, name="renamed"), 6),
                        "name changed content")
                require(result["external_claim_truth"] == "not_assessed", "truth")
                require(result["historical_V1"] == "preserved_as_dated_record", "history")
                require(result["current_position"] == "not_certified_from_local_cache",
                        "cache promoted to present certainty")

    registered = tuple(make_replica(f"D{i + 1}", v)
                       for i, v in enumerate((2, 1, 0, 2)))
    partial = coverage(events, registered, 6)
    all_done = tuple(make_replica(f"D{i + 1}", 2) for i in range(4))
    known = coverage(events, all_done, 6)
    hidden = project(events, make_replica("unregistered_print", 0), 6)
    require(known["complete_within_registry"] and
            hidden["local_as_of_values"]["pause_request"], "hidden-copy example")

    # Two authored worlds have the same local record but different source states.
    # In world B the withdrawal does not occur until after the query.
    later_events = (BASE, replace(both, issued=7))
    isolated = make_replica("isolated", 0)
    same_local = project(events, isolated, 6) == project(later_events, isolated, 6)
    def source_state(ledger):
        state = {}
        for event in sorted(ledger, key=lambda e: e.revision):
            if event.issued <= 6:
                state.update(event.changes)
        return state
    different_source = source_state(events) != source_state(later_events)
    require(same_local and different_source, "indistinguishable local worlds")

    baseline_replica = make_replica("copy", 2)
    bad = {
        "duplicate_revision": ((BASE, replace(both, revision=1)), baseline_replica),
        "duplicate_id": ((BASE, replace(both, eid="G1")), baseline_replica),
        "unknown_scope": ((BASE, replace(both, changes=(("truth", False),))), baseline_replica),
        "wrong_target": ((BASE, replace(both, target="OTHER")), baseline_replica),
        "backwards_event_time": ((BASE, replace(both, issued=1)), baseline_replica),
        "unknown_receipt": (events, replace(baseline_replica, received=(("X", 4),))),
        "premature_receipt": (events, replace(baseline_replica, received=(("G1", 2), ("W2", 3)))),
        "apply_without_receipt": (events, replace(baseline_replica, received=(("G1", 2),))),
        "apply_before_receipt": (events, replace(baseline_replica, applied=(("G1", 2), ("W2", 3)))),
    }
    for label, (ledger, replica) in bad.items():
        try:
            project(ledger, replica, 6)
        except ValueError:
            pass
        else:
            raise AssertionError(label)
    require((events, SOURCE) == original, "history mutated")
    compact = {k: {"values": v["local_as_of_values"], "pending": v["pending_events"],
                   "new_use": v["new_named_support_use"]} for k, v in named.items()}
    print(json.dumps({
        "model": "E026-scoped-withdrawal-v1",
        "kind": "authored_fixtures_not_empirical_results",
        "named_cases": compact,
        "delivery_configurations": 81, "scope_variants": 3,
        "global_states_checked": configurations, "replica_views_checked": views,
        "partial_delivery_at_6": partial,
        "late_and_duplicate_grant_does_not_resurrect": True,
        "hidden_copy_counterexample": {
            "registry_complete": known["complete_within_registry"],
            "unregistered_copy_still_has_old_request": hidden["local_as_of_values"]["pause_request"],
            "global_completion": known["global_completion"]},
        "undelivered_update_counterexample": {
            "local_views_identical": same_local,
            "source_states_differ_at_query": different_source,
            "current_position": "not_certified_from_local_cache"},
        "malformed_inputs_rejected": list(bad),
        "verified": ["scoped_changes", "receipt_is_not_application", "dated_history_retained",
                     "order_and_retry_invariance", "no_cache_to_present_promotion",
                     "no_truth_inference", "bounded_completion_only"],
        "not_verified": ["authenticity", "free_consent", "semantic_scope_extraction",
                         "all_copies_discovered", "actual_human_reading", "legal_effect",
                         "later_reendorsement"],
        "status": "PASS"
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
