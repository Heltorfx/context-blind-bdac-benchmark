"""Integration check against a running exhibition server (uses real crypto)."""
import http.cookiejar
import json
import os
import urllib.error
import time
import urllib.request


def client():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def call(opener, path, post=False, admin=False):
    headers = {'X-Admin-Key':os.environ['VEIL_ADMIN_KEY']} if admin else {}
    body = json.dumps({'indexes':[4,7,10,15]}).encode() if path == '/api/present' else b''
    request = urllib.request.Request('http://localhost:8766' + path, data=body if post else None, headers=headers)
    with opener.open(request, timeout=10) as response:
        return json.load(response)


def wait(opener, status):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        state = call(opener, '/api/state')
        if state['wallet'].get('status') == 'error':
            raise AssertionError('Protocol failed')
        if state['wallet'].get('status') == status and not state['wallet'].get('busy'):
            return state
        time.sleep(.5)
    raise TimeoutError(status)


def main():
    alice, bob = client(), client()
    call(alice, '/api/join', True)
    call(bob, '/api/join', True)
    call(alice, '/api/issue', True)
    enrolled = wait(alice, 'ready')['wallet']
    assert len(enrolled['attributes']) == 16
    assert len(enrolled['profile']) == 16
    for item in enrolled['profile']:
        assert bytes.fromhex(item['value']).lstrip(b'\0').decode('ascii') == item['text']
    assert not call(bob, '/api/state')['wallet']['credential']
    assert 'attributes' not in call(bob, '/api/state')['wallet']
    for action in ('accept', 'reject'):
        call(alice, '/api/present', True)
        state = wait(alice, 'prepared')
        assert len(state['wallet']['disclosed']) == 4
        assert [a['index'] for a in state['wallet']['disclosed']] == [4,7,10,15]
        assert state['wallet']['metrics']['proof_kb'] > 0
        assert 'user' not in state['wallet'] and 'se' not in state['wallet']
        ticket = state['wallet']['ticket']
        for item in state['wallet']['disclosed']:
            assert item['value'] == enrolled['attributes'][item['index']]
        with alice.open('http://localhost:8766/presentation-qr.png') as response:
            assert response.read().startswith(b'\x89PNG')
        try:
            call(alice, '/api/accept?ticket='+ticket, True)
            raise AssertionError('Visitor authorized as admin')
        except urllib.error.HTTPError as error:
            assert error.code == 403
        if os.environ.get('VEIL_ADMIN_KEY'):
            review = call(bob, '/api/review?ticket='+ticket, admin=True)
            assert review['disclosed'] == state['wallet']['disclosed']
            assert 'attributes' not in review and 'user' not in review
            call(bob, '/api/'+action+'?ticket='+ticket, True, admin=True)
            assert call(alice, '/api/state')['wallet']['decision'] == ('accepted' if action=='accept' else 'rejected')
            try:
                call(bob, '/api/accept?ticket='+ticket, True, admin=True)
                raise AssertionError('Duplicate decision accepted')
            except urllib.error.HTTPError as error:
                assert error.code == 409
    print('PASS: real issuance, repeatable ZK presentation, session isolation and public response filtering')


if __name__ == '__main__':
    main()
