"""Fictional exhibition attributes, encoded directly in field-safe bytes."""
import secrets

LABELS = ('First name', 'Age', 'Place of birth', 'Sex', 'Height', 'Nationality',
          'City of residence', 'Language', 'Occupation', 'Membership', 'Access zone',
          'Ticket type', 'Favourite colour', 'Favourite sport', 'Year joined', 'Group')


def generate_attributes(pp):
    choose = secrets.choice
    values = (choose(('Alice', 'Leo', 'Emma', 'Noah', 'Camille', 'Alex', 'Nora', 'Sam')),
              str(18 + secrets.randbelow(63)),
              choose(('Paris', 'Berlin', 'Brussels', 'Lyon', 'Rome', 'Lisbon')),
              choose(('Female', 'Male')), str(150 + secrets.randbelow(51)) + ' cm',
              choose(('French', 'German', 'Belgian', 'Italian', 'Portuguese')),
              choose(('Lille', 'Munich', 'Ghent', 'Nice', 'Porto')),
              choose(('French', 'English', 'German', 'Italian')),
              choose(('Student', 'Researcher', 'Teacher', 'Designer', 'Engineer')),
              choose(('Member', 'Guest', 'Volunteer')), choose(('Hall A', 'Hall B', 'Hall C')),
              choose(('Day pass', 'Full event')), choose(('Green', 'Blue', 'Red', 'Yellow')),
              choose(('Swimming', 'Running', 'Tennis', 'Cycling')),
              str(2020 + secrets.randbelow(7)), choose(('Alpha', 'Beta', 'Gamma')))
    encoded = tuple(value.encode('ascii').rjust(pp.attribute_size, b'\0') for value in values)
    if len(encoded) != pp.attribute_count or any(len(a) != pp.attribute_size or int.from_bytes(a, 'big') >= pp.field_order for a in encoded):
        raise ValueError('Demo profile does not fit the attribute parameters')
    return encoded


def describe(index, value):
    return dict(index=int(index), label=LABELS[index], text=value.lstrip(b'\0').decode('ascii'), value=value.hex())
