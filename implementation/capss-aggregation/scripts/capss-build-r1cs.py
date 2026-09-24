import argparse
parser = argparse.ArgumentParser()
parser.add_argument('scheme_label', help='Signature label')
parser.add_argument('msg_size', type=int, help='Message size')
arguments = parser.parse_args()

scheme_label = arguments.scheme_label
msg_size = arguments.msg_size

DIRPATH = '.'
FILENAME_FIELD_PARAMETERS = f'{DIRPATH}/r1cs-field.txt'
FILENAME_R1CS_CONSTRAINTS = f'{DIRPATH}/r1cs-constraints.txt'

## Get the signature scheme
from capss.sign.instances import get_scheme
scheme = get_scheme(f'{scheme_label}.extended')
print(f'Signature Scheme: {scheme_label}')

### Build R1CS Constraints
from r1cs.r1cs import R1CS
r1cs = R1CS(scheme.get_field())
from utils.log import Log
Log.set_verbose(False)

print(f'Building R1CS system...')
from capss.sign.r1cs import build_r1cs_for_verification
r1cs = build_r1cs_for_verification(scheme, msg_size)
print(f' - Nb R1CS variables: {r1cs.get_nb_variables()}')
print(f' - Nb R1CS equations: {r1cs.get_nb_equations()}')

from capss.libiop.export_r1cs import export_field_params, export_r1cs
export_field_params(scheme.get_field().order(), FILENAME_FIELD_PARAMETERS, verbose=False)
print(f'Output: Field parameters saved in {FILENAME_FIELD_PARAMETERS}')
export_r1cs(r1cs, FILENAME_R1CS_CONSTRAINTS)
print(f'Output: R1CS constraints saved in {FILENAME_R1CS_CONSTRAINTS}')

