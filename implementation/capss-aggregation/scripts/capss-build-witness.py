import argparse
parser = argparse.ArgumentParser()
parser.add_argument('filenames', nargs='+', help='Files that contain the signatures')
arguments = parser.parse_args()
filenames = arguments.filenames
assert len(filenames)

DIRPATH = '.'
FILENAME_R1CS_PRIMARY_INPUTS = f'{DIRPATH}/r1cs-primary-inputs.txt'
FILENAME_R1CS_AUX_INPUTS = f'{DIRPATH}/r1cs-auxiliary-inputs.txt'

def parse(filename):
    import json
    with open(filename) as _file:
        return json.loads(_file.read())

data = []
data.append(parse(filenames[0]))
scheme_label = data[0]['sig_label']
msg_size = len(data[0]['msg'])

for filename in filenames[1:]:
    data.append(parse(filename))
    assert scheme_label == data[-1]['sig_label']
    assert msg_size == len(data[-1]['msg'])

from capss.sign.instances import get_scheme
scheme = get_scheme(f'{scheme_label}.extended')
print(f'Signature Scheme: {scheme_label}')
print(f'Nb signatures: {len(data)}')

print(f'Recovering R1CS system...')
from utils.log import Log
Log.set_verbose(False)

from capss.sign.r1cs import build_r1cs_for_verification
r1cs = build_r1cs_for_verification(scheme, msg_size)

print(f'Resolving variable assignment...')
from capss.sign.r1cs import build_inputs
all_inputs = []
all_variables = []
for sigdata in data:
    inputs = build_inputs(scheme, sigdata['pk'], sigdata['msg'], sigdata['sig'])
    variables = r1cs.resolve(inputs, verbose=True)
    all_inputs.append(inputs)
    all_variables.append(variables)

from capss.libiop.export_r1cs import export_variables
export_variables(r1cs, all_inputs,
    FILENAME_R1CS_PRIMARY_INPUTS, FILENAME_R1CS_AUX_INPUTS,
    precomputed_variables=all_variables
)
print(f'Output: Primary inputs saved in {FILENAME_R1CS_PRIMARY_INPUTS}')
print(f'Output: Auxiliary inputs saved in {FILENAME_R1CS_AUX_INPUTS}')
