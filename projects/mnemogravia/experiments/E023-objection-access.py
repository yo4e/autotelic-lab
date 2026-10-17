"""E023: fictional access-to-objection model, not empirical evidence.

Python 3.10+, standard library only; no file writes or network calls.
One reversible provisional-use docket, sixteen weeks, one review slot/week.
"""
from collections import defaultdict, deque
from dataclasses import dataclass
import json


@dataclass(frozen=True)
class Person:
    name: str
    money: int
    hours: float


@dataclass(frozen=True)
class Petition:
    week: int
    person: str
    ground: str
    material: bool       # Stipulated independent of the intake officer's view.
    prima_facie: bool    # An imperfect visible intake signal.


@dataclass(frozen=True)
class Policy:
    name: str
    fee: int
    effort: float
    screen: bool


PEOPLE = (
    Person('time_poor', 0, .75),
    Person('cash_poor', 2, 3),
    Person('resourced', 200, 20),
    Person('late_affected', 0, 1),
    Person('hard_to_articulate', 0, .75),
    Person('repeat_filer', 1000, 100),
)
POLICIES = (
    Policy('open_automatic_stay', 0, 1, False),
    Policy('paid_automatic_stay', 12, 1, False),
    Policy('assisted_scoped_review', 0, .5, True),
)
WEEKS = 16
REVIEW_CAPACITY = 1


def events():
    claims = [
        Petition(0, 'time_poor', 'unlisted_witness', True, True),
        Petition(0, 'cash_poor', 'changed_use', True, True),
        Petition(0, 'resourced', 'document_conflict', True, True),
        Petition(4, 'late_affected', 'omitted_stakeholder', True, True),
        Petition(8, 'hard_to_articulate', 'unrecognized_harm', True, False),
    ]
    claims += [Petition(w, 'repeat_filer', 'unchanged_objection', False, False)
               for w in range(12)]
    claims.append(Petition(6, 'repeat_filer', 'novel_looking_noise', False, True))
    return tuple(sorted(claims, key=lambda c: c.week))


EVENTS = events()


def simulate(policy):
    money = {p.name: p.money for p in PEOPLE}
    time = {p.name: p.hours for p in PEOPLE}
    queue, seen = deque(), set()
    counts = defaultdict(int)
    filed, heard, delays = set(), set(), {}
    held_weeks, max_queue = [], 0

    for week in range(WEEKS):
        for e in (e for e in EVENTS if e.week == week):
            if money[e.person] < policy.fee:
                counts['fee_barrier'] += 1
                continue
            if time[e.person] + 1e-9 < policy.effort:
                counts['time_barrier'] += 1
                continue
            money[e.person] -= policy.fee
            time[e.person] -= policy.effort
            counts['filed_petitions'] += 1
            if e.material:
                filed.add(e.person)
            key = (e.person, e.ground)  # Same person and same ground only.
            if policy.screen and key in seen:
                counts['duplicates_merged'] += 1
                continue
            seen.add(key)
            if policy.screen and not e.prima_facie:
                counts['screened_out'] += 1
                counts['material_screened_out'] += int(e.material)
                continue
            queue.append(e)
            counts['admitted_for_review'] += 1

        max_queue = max(max_queue, len(queue))
        if queue:
            held_weeks.append(week)  # A pending docket pauses this whole week.
        for _ in range(REVIEW_CAPACITY):
            if not queue:
                break
            e = queue.popleft()  # Review is not a finding of truth or merit.
            counts['reviews'] += 1
            if e.material:
                heard.add(e.person)
                delays[e.person] = week - e.week
            else:
                counts['noise_reviews'] += 1

    material_people = {e.person for e in EVENTS if e.material}
    return {
        'policy': policy.name,
        'material_filed': len(filed),
        'material_heard': len(heard),
        'material_unheard': sorted(material_people - heard),
        'held_weeks': len(held_weeks),
        'hold_week_indices': held_weeks,
        'maximum_queue': max_queue,
        'pending_after_week_15': len(queue),
        'material_review_delay_weeks': delays,
        'counts': dict(sorted(counts.items())),
    }


def test(results):
    a, b, c = results
    assert len(EVENTS) == 18 and sum(e.material for e in EVENTS) == 5
    assert (a['material_filed'], b['material_filed'], c['material_filed']) == (3, 1, 5)
    assert (a['material_heard'], b['material_heard'], c['material_heard']) == (3, 1, 4)
    assert (a['held_weeks'], b['held_weeks'], c['held_weeks']) == (16, 14, 5)
    assert c['counts']['duplicates_merged'] == 11
    assert c['counts']['material_screened_out'] == 1
    assert c['counts']['noise_reviews'] == 1
    assert c['material_unheard'] == ['hard_to_articulate']
    assert b['counts']['noise_reviews'] == 13  # A wealthy repeater passes a fee gate.
    assert all(r['pending_after_week_15'] == 0 for r in results)
    return ['cost_filters_capacity_not_merit', 'wealthy_repetition_survives_fee',
            'dedup_reduces_repeat_holds', 'triage_has_false_negative_and_positive',
            'review_does_not_imply_truth', 'finite_horizon_only']


def main():
    results = [simulate(p) for p in POLICIES]
    print(json.dumps({
        'model': 'E023-objection-access-v1',
        'kind': 'constructed_fictional_cases_not_empirical_results',
        'weeks': WEEKS,
        'weekly_review_capacity': REVIEW_CAPACITY,
        'material_claimants': 5,
        'noise_petitions': 13,
        'policies': results,
        'checks': test(results),
        'status': 'PASS',
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
