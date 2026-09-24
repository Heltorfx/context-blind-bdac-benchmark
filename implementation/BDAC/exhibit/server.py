"""Run from Implementation: python -m BDAC.exhibit.server --port 8766."""
import argparse
import io
import json
import logging
import queue
import secrets
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from .attributes import generate_attributes, describe

STATIC = Path(__file__).with_name('static')


class Exhibit:
    def __init__(self, public_url):
        self.public_url = public_url.rstrip('/')
        self.lock = threading.RLock()
        self.jobs = queue.Queue(maxsize=24)
        self.wallets = {}
        self.events = []
        self.ready = False
        self.failed = False
        self.issued = 0
        self.accepted = 0
        self.latest = None
        self.tickets = {}
        self.admin_key = secrets.token_urlsafe(32)

    def event(self, title, detail, phase='working'):
        with self.lock:
            self.events.append(dict(title=title, detail=detail, phase=phase, at=time.time()))
            self.events = self.events[-30:]

    def reset(self):
        with self.lock:
            if self.jobs.unfinished_tasks or any(wallet.get('busy') for wallet in self.wallets.values()):
                return False
            self.wallets = {
                token: dict(status='new', credential=False, busy=False)
                for token in self.wallets
            }
            self.events = []
            self.issued = 0
            self.accepted = 0
            self.latest = None
            self.tickets = {}
            self.event('Demonstration reset', 'Wallets, presentations and counters were cleared.', 'done')
            return True

    def worker(self):
        try:
            from BDAC import Setup, User, SE, Issuer, Verifier, GovernanceAuthority, Enrollment, Issuance, Presentation
            from BDAC.core.policies import VerifierPolicy
            from BDAC.proofs import precompute_show_r1cs_template
            from BDAC.proofs.aurora_backend import AuroraBackend
            pp = Setup()
            issuer = Issuer(pp)
            class DemoGovernance(GovernanceAuthority):
                def issue_attributes(self):
                    from BDAC.core.types import AttributeVector
                    return AttributeVector(generate_attributes(self.pp))
            governance = DemoGovernance(pp)
            self.event('Preparing the cryptography', 'CAPSS keys and Aurora-CF circuit')
            precompute_show_r1cs_template()
            with self.lock:
                self.ready = True
            self.event('Cryptographic setup complete', 'CAPSS and Aurora-CF are available for the live protocol.', 'done')
        except Exception:
            logging.exception('Exhibit initialization failed')
            self.failed = True
            self.event('Initialization failed', 'Check the server terminal and restart.', 'error')
            return
        while True:
            token, action = self.jobs.get()
            wallet = self.wallets[token]
            started = time.perf_counter()
            try:
                with self.lock:
                    wallet['status'] = action
                    wallet['stage'] = 'Creating your fictional profile' if action == 'issuing' else 'Requesting the device signature'
                if action == 'issuing':
                    self.event('Enrollment', 'Governance → User · 16 random field attributes')
                    se = SE(pp)
                    user = User(pp, se)
                    Enrollment().run(user, governance)
                    with self.lock:
                        wallet['stage'] = 'Building the attribute tree and signing the credential'
                    self.event('Issuance', 'User → Issuer · attributes and device public key · issuer builds the attribute tree')
                    result = Issuance().run(user, issuer)
                    if not result.ok:
                        raise RuntimeError('Issuance rejected')
                    with self.lock:
                        wallet.update(user=user, se=se, attributes=[a.hex() for a in user.attributes], profile=[describe(i,a) for i,a in enumerate(user.attributes)], credential=True, status='ready', elapsed=time.perf_counter()-started)
                        self.issued += 1
                    self.event('Credential issued', f'Issuer signature verified · {result.message_sizes["total"]/1000:.2f} KB', 'done')
                else:
                    exhibit = self
                    class ObservedBackend(AuroraBackend):
                        def prove_show(self, instance):
                            with exhibit.lock:
                                wallet['stage'] = 'Generating and verifying the Aurora ZK proof'
                            exhibit.event('Device contribution received', 'SE signed the committed challenge · device key stays private')
                            exhibit.event('Generating the presentation', 'Aurora-CF · credential, device signature and Merkle openings')
                            return super().prove_show(instance)
                    indexes = tuple(wallet['requested_indexes'])
                    verifier = Verifier(pp, policy=VerifierPolicy('exhibit', presentation_indexes=indexes))
                    self.event('Presentation requested', 'Verifier → User · fresh challenge and indexes ' + ', '.join(map(str,indexes)))
                    result = Presentation(proof_backend=ObservedBackend(version='v2')).run(wallet['user'], verifier, wallet['se'])
                    if not result.ok:
                        raise RuntimeError('Presentation rejected')
                    raw = result.aurora_result
                    metrics = dict(prove=raw['prove_seconds'], verify=raw['verify_seconds'], proof_kb=raw['proof_size_bytes']/1000, total_kb=result.message_sizes['total']/1000)
                    disclosed = [describe(i,a) for i, a in zip(result.disclosure.indexes, result.disclosure.attributes)]
                    with self.lock:
                        ticket = secrets.token_urlsafe(24)
                        self.tickets[ticket] = dict(disclosed=disclosed, metrics=metrics, valid=True, decision='pending', expires=time.time()+600)
                        wallet.update(status='prepared', ticket=ticket, metrics=metrics, disclosed=disclosed, elapsed=time.perf_counter()-started)
                        self.latest = metrics
                    self.event('Presentation ready', f'Proof verified · {metrics["proof_kb"]:.2f} KB · awaiting desk approval', 'done')
            except Exception:
                logging.exception('Protocol failed')
                with self.lock:
                    wallet['status'] = 'error'
                self.event('Operation failed', 'The visitor can retry. Details are available on the server.', 'error')
            finally:
                with self.lock:
                    wallet['busy'] = False
                self.jobs.task_done()

    def snapshot(self, token):
        with self.lock:
            wallet = self.wallets.get(token, {})
            ticket = self.tickets.get(wallet.get('ticket'))
            return dict(ready=self.ready, failed=self.failed, public_url=self.public_url,
                        issued=self.issued, accepted=self.accepted, queued=self.jobs.qsize(),
                        events=self.events[-8:], latest=self.latest,
                        wallet={**{k:wallet[k] for k in ('status','credential','attributes','profile','stage','metrics','disclosed','elapsed','busy','ticket') if k in wallet},
                                'decision': ('expired' if ticket['decision'] == 'pending' and ticket['expires'] < time.time() else ticket['decision']) if ticket else None})


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def token(self):
        try:
            cookie = SimpleCookie(self.headers.get('Cookie', ''))
            return cookie['bdac_session'].value if 'bdac_session' in cookie else None
        except Exception:
            return None

    def send(self, status, body, content_type='application/json', cookie=None):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if cookie:
            self.send_header('Set-Cookie', f'bdac_session={cookie}; HttpOnly; SameSite=Strict; Path=/')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/api/accepted':
            if not self.is_admin():
                return self.send(403, {'error':'Administrator access required.'})
            with self.server.exhibit.lock:
                accepted = [dict(ticket=key, disclosed=item['disclosed'], accepted_at=item['decided_at'])
                            for key, item in self.server.exhibit.tickets.items() if item['decision'] == 'accepted']
                return self.send(200, {'presentations':sorted(accepted, key=lambda item:item['accepted_at'], reverse=True)})
        if path == '/api/review':
            if not self.is_admin():
                return self.send(403, {'error':'Open the private administrator link first.'})
            ticket_id = parse_qs(urlsplit(self.path).query).get('ticket', [''])[0]
            with self.server.exhibit.lock:
                ticket = self.server.exhibit.tickets.get(ticket_id)
                if not ticket:
                    return self.send(404, {'error':'Presentation not found.'})
                return self.send(200, {**ticket, 'expired': ticket['expires'] < time.time()})
        if path == '/api/state':
            return self.send(200, self.server.exhibit.snapshot(self.token()))
        if path in ('/qr.png', '/presentation-qr.png', '/admin-qr.png'):
            import qrcode
            url = self.server.exhibit.public_url
            if path == '/admin-qr.png':
                url += '/admin#key=' + self.server.exhibit.admin_key
            elif path == '/presentation-qr.png':
                with self.server.exhibit.lock:
                    wallet = self.server.exhibit.wallets.get(self.token(), {})
                    ticket = wallet.get('ticket')
                if not ticket:
                    return self.send(404, {'error':'No presentation'})
                url += '/admin?ticket=' + ticket
            data = io.BytesIO()
            qrcode.make(url).save(data, format='PNG')
            return self.send(200, data.getvalue(), 'image/png')
        files = {'/':'index.html', '/screen':'index.html', '/admin':'admin.html', '/admin-qr':'admin-qr.html', '/admin.js':'admin.js', '/app.js':'app.js', '/style.css':'style.css', '/lions-mark.png':'lions-mark.png', '/facet-texture.png':'facet-texture.png'}
        if path not in files:
            return self.send(404, {'error':'Not found'})
        mime = {'html':'text/html; charset=utf-8', 'css':'text/css', 'js':'text/javascript', 'png':'image/png'}
        filename = files[path]
        return self.send(200, (STATIC / filename).read_bytes(), mime[filename.rsplit('.',1)[1]])

    def is_admin(self):
        return secrets.compare_digest(self.headers.get('X-Admin-Key', ''), self.server.exhibit.admin_key)

    def do_POST(self):
        if self.headers.get('Origin') and urlsplit(self.headers['Origin']).netloc != self.headers.get('Host'):
            return self.send(403, {'error':'Origin rejected'})
        exhibit = self.server.exhibit
        path = urlsplit(self.path).path
        if path == '/api/reset':
            if self.client_address[0] not in ('127.0.0.1', '::1'):
                return self.send(403, {'error':'Reset is only available from the server.'})
            if not exhibit.reset():
                return self.send(409, {'error':'A cryptographic operation is still running.'})
            return self.send(200, {'ok':True})
        with exhibit.lock:
            if path in ('/api/accept', '/api/reject'):
                if not self.is_admin():
                    return self.send(403, {'error':'Administrator access required.'})
                ticket_id = parse_qs(urlsplit(self.path).query).get('ticket', [''])[0]
                ticket = exhibit.tickets.get(ticket_id)
                if not ticket:
                    return self.send(404, {'error':'Presentation not found.'})
                if ticket['expires'] < time.time() or ticket['decision'] != 'pending':
                    return self.send(409, {'error':'Presentation expired or already reviewed.'})
                if not ticket['valid']:
                    return self.send(409, {'error':'Invalid proof.'})
                ticket['decision'] = 'accepted' if path == '/api/accept' else 'rejected'
                ticket['decided_at'] = time.time()
                if ticket['decision'] == 'accepted':
                    exhibit.accepted += 1
                exhibit.event('Desk decision', 'Presentation ' + ticket['decision'], 'done')
                return self.send(200, {'ok':True})
            if path == '/api/join':
                token = self.token()
                if token not in exhibit.wallets:
                    if len(exhibit.wallets) >= 200:
                        return self.send(503, {'error':'Session capacity reached'})
                    token = secrets.token_urlsafe(32)
                    exhibit.wallets[token] = dict(status='new', credential=False, busy=False)
                return self.send(200, {'ok':True}, cookie=token)
            wallet = exhibit.wallets.get(self.token())
            if wallet is None:
                return self.send(401, {'error':'Join the demonstration first'})
            if path not in ('/api/issue','/api/present'):
                return self.send(404, {'error':'Not found'})
            if not exhibit.ready or wallet['busy']:
                return self.send(409, {'error':'Please wait for the current operation'})
            if path == '/api/issue' and wallet['credential']:
                return self.send(409, {'error':'Your credential is already issued'})
            if path == '/api/present' and not wallet['credential']:
                return self.send(409, {'error':'Create your credential first'})
            action = 'issuing' if path == '/api/issue' else 'presenting'
            if action == 'presenting':
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    if not 0 < length <= 1024:
                        raise ValueError()
                    payload = json.loads(self.rfile.read(length))
                    indexes = payload.get('indexes')
                    if not isinstance(indexes, list) or len(indexes) != 4 or any(type(i) is not int or not 0 <= i < 16 for i in indexes) or len(set(indexes)) != 4:
                        raise ValueError()
                except (ValueError, AttributeError, UnicodeError):
                    return self.send(400, {'error':'Select exactly four distinct attributes.'})
                wallet['requested_indexes'] = sorted(indexes)
            try:
                exhibit.jobs.put_nowait((self.token(), action))
            except queue.Full:
                return self.send(503, {'error':'Queue full. Please try again shortly.'})
            wallet.update(busy=True, status='queued', stage='Waiting for the cryptographic engine')
            if action == 'presenting':
                wallet.pop('ticket', None)
            return self.send(202, {'ok':True})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--public-url')
    args = parser.parse_args()
    public_url = args.public_url or f'http://192.168.137.1:{args.port}'
    server = ThreadingHTTPServer(('0.0.0.0', args.port), Handler)
    server.exhibit = Exhibit(public_url)
    print(f'Wallet: {public_url}\nDisplay: http://localhost:{args.port}/screen', flush=True)
    print(f'Private admin: {public_url}/admin#key={server.exhibit.admin_key}', flush=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    server.exhibit.worker()


if __name__ == '__main__':
    main()
