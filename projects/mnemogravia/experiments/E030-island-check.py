"""E030: fictional two-island publication / delivery / access fixtures.

Not empirical readership data or a rights authenticator. Python 3.10+,
standard library only. No network or file writes; output is JSON to stdout.
"""
from dataclasses import dataclass
from itertools import product
import json

DAYS = tuple(range(6))
PORTS = ('East', 'West')
PLANS = ('latest_only', 'backfill', 'supplement')
BINDINGS = ('verified_C', 'unresolved', 'verified_A')
ACCESS = ('west_closed_day_3', 'west_open_day_3')


@dataclass(frozen=True)
class Parcel:
    port: str
    day: int
    object_id: str
    kind: str  # issue or separate supplement
    contains_name: bool


def public_open(port: str, day: int, access: str) -> bool:
    return not (port == 'West' and day == 3 and access == 'west_closed_day_3')


def first_public_day(parcel: Parcel, access: str) -> int | None:
    return next((day for day in DAYS if day >= parcel.day and public_open(parcel.port, day, access)), None)


def simulate(binding: str, plan: str, access: str) -> dict:
    if (binding not in BINDINGS or plan not in PLANS or access not in ACCESS):
        raise ValueError('unknown model configuration')
    # External confirmation of target C and separately valid A permit a new
    # named row. The model cannot verify either of these assumptions.
    may_reprint = binding == 'verified_C'
    payload = {'I0': False, 'I1': may_reprint, 'I2': False}
    deliveries = [
        Parcel('East', 0, 'I0', 'issue', False),
        Parcel('West', 0, 'I0', 'issue', False),
        Parcel('East', 1, 'I1', 'issue', payload['I1']),
        Parcel('East', 2, 'I2', 'issue', False),
        Parcel('West', 3, 'I2', 'issue', False),
    ]
    if plan == 'backfill':
        deliveries.append(Parcel('West', 3, 'I1', 'issue', payload['I1']))
    if plan == 'supplement' and may_reprint:
        # A supplement is not retrospectively issue I0 or the missing I1.
        deliveries.append(Parcel('West', 2, 'S1', 'supplement', True))
    deliveries = sorted(deliveries, key=lambda p: (p.day, p.port, p.object_id))
    ports = {}
    for port in PORTS:
        sent = [p for p in deliveries if p.port == port]
        named = [p for p in sent if p.contains_name]
        named_I1 = [p for p in named if p.object_id == 'I1']
        first_available = min((first_public_day(p, access) for p in named), default=None)
        first_i1 = min((first_public_day(p, access) for p in named_I1), default=None)
        first_received = min((p.day for p in named), default=None)
        latest_issue_at_day5 = max((p for p in sent if p.kind == 'issue' and p.day <= 5),
                                   key=lambda p: (int(p.object_id[1:]), p.day))
        ports[port] = {
            'first_named_physically_received': first_received,
            'first_named_publicly_available': first_available,
            'I1_physically_received': min((p.day for p in named_I1), default=None),
            'I1_publicly_available': first_i1,
            'latest_issue_at_day5': latest_issue_at_day5.object_id,
            'received_objects': [p.object_id for p in sent],
        }
    return {
        'binding': binding, 'plan': plan, 'access': access,
        'I1_named_at_source': may_reprint,
        'source_publication_day_I1': 1,
        'ports': ports,
        'day0_missed_issue_rewritten': False,
        'read_or_understood': 'not_measured',
    }


def check(ok: bool, why: str) -> None:
    if not ok:
        raise AssertionError(why)


def main() -> None:
    results = [simulate(*cfg) for cfg in product(BINDINGS, PLANS, ACCESS)]
    for result in results:
        e, w = result['ports']['East'], result['ports']['West']
        check(e['latest_issue_at_day5'] == w['latest_issue_at_day5'] == 'I2', 'latest end state')
        check(result['day0_missed_issue_rewritten'] is False, 'no time reversal')
        for port in (e, w):
            receive, available = port['first_named_physically_received'], port['first_named_publicly_available']
            check(receive is None and available is None if receive is None else
                  available is not None and available >= receive, 'no pre-receipt access')
            check(port['I1_publicly_available'] is None if port['I1_physically_received'] is None
                  else port['I1_publicly_available'] >= port['I1_physically_received'], 'I1 access')
        if result['binding'] != 'verified_C':
            check(not result['I1_named_at_source'], 'no unverified reissue')
            check(e['first_named_publicly_available'] is None and
                  w['first_named_publicly_available'] is None, 'no borrowed authorization')
        else:
            check(e['first_named_publicly_available'] == 1, 'east access')
            want = {'latest_only': None, 'backfill': 4 if result['access'] == 'west_closed_day_3' else 3,
                    'supplement': 2}[result['plan']]
            check(w['first_named_publicly_available'] == want, 'west access schedule')
            if result['plan'] == 'supplement':
                check(w['I1_physically_received'] is None, 'supplement not I1')
            if result['plan'] == 'backfill':
                check(w['I1_physically_received'] == 3, 'backfill receipt')

    named = {f'{plan}/{access}': simulate('verified_C', plan, access)['ports']['West']
             for plan in PLANS for access in ACCESS}
    latest = simulate('verified_C', 'latest_only', 'west_closed_day_3')['ports']['West']
    backfill = simulate('verified_C', 'backfill', 'west_closed_day_3')['ports']['West']
    check(latest['latest_issue_at_day5'] == backfill['latest_issue_at_day5']
          and latest['I1_publicly_available'] != backfill['I1_publicly_available'],
          'identical latest edition hides different archive')
    invalid = 0
    for case in [('unknown', 'backfill', ACCESS[0]), (BINDINGS[0], 'wrong', ACCESS[0]),
                 (BINDINGS[0], PLANS[0], 'wrong')]:
        try:
            simulate(*case)
        except ValueError:
            invalid += 1
        else:
            raise AssertionError('accepted invalid configuration')
    print(json.dumps({
        'model': 'E030-islands-and-missed-editions-v1',
        'kind': 'fictional_schedules_not_empirical_delivery_or_reading',
        'combinations_checked': len(results),
        'first_named_public_availability_west': {name: data['first_named_publicly_available']
                                                   for name, data in named.items()},
        'example': simulate('verified_C', 'backfill', 'west_closed_day_3'),
        'counterexamples': {
            'latest_only_no_named_form_by_day5': latest['first_named_publicly_available'] is None,
            'same_latest_I2_different_I1_access': True,
            'backfilled_I1_reaches_west_on_day3_but_accessible_on_day4':
                backfill['I1_physically_received'] == 3 and backfill['I1_publicly_available'] == 4,
            'supplement_is_not_I1': 'I1' not in simulate('verified_C', 'supplement', ACCESS[0])['ports']['West']['received_objects'],
            'no_retroactive_day0_slot': True,
        },
        'invalid_configurations_rejected': invalid,
        'not_verified': ['real consent', 'binding authenticity', 'readers or comprehension',
                         'harms or benefits', 'unobserved routes', 'rights to publish'],
        'status': 'PASS',
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
