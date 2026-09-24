import argparse
parser = argparse.ArgumentParser()
parser.add_argument('scheme_label', help='Signature label')
parser.add_argument('msg_size', type=int, help='Message size')
parser.add_argument('out_filename', help='Output file name')
arguments = parser.parse_args()

scheme_label = arguments.scheme_label
msg_size = arguments.msg_size
out_filename = arguments.out_filename

## Get the signature scheme
from capss.sign.instances import get_scheme
scheme = get_scheme(f'{scheme_label}.extended')
print(f'Signature Scheme: {scheme_label}')

import sys
from utils.log import Log
Log.set_verbose(False)

field = scheme.get_field()
msg = [field.random_element() for _ in range(msg_size)]

# Key Generation
print(' - KeyGen: ', end=''); sys.stdout.flush()
pk, sk = scheme.keygen()
print('done')

# Signing
print(' - Signing: ', end=''); sys.stdout.flush()
sig = scheme.sign(sk, msg)
print('done')

# Verification
print(' - Verification: ', end=''); sys.stdout.flush()
assert scheme.verify(pk, msg, sig)
print('done')

import json
with open(out_filename, 'w') as _file:
    _file.write(json.dumps({
        'sig_label': scheme_label,
        'msg': [int(x) for x in msg],
        'pk': [int(x) for x in pk],
        'sig': [int(x) for x in sig],
    }))
print(f'Output: Signature saved in {out_filename}')
