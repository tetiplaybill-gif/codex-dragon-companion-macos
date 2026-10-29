"""Account-free public announcements with separate source health and receipts.

Codex Resets is a third-party report, never evidence of an account refill or a
direct read of X. No cookies, tokens, login data, or old X caches are consumed.
"""
import copy
import hashlib
import json
import math
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
import xml.etree.ElementTree as ET

MAX_BYTES = 1024 * 1024
MAX_RSS_BYTES = 16 * MAX_BYTES
MAX_CACHE_BYTES = 4 * MAX_BYTES
MAX_ITEMS = 100
MAX_TEXT = 25000
MAX_BACKOFF = 86400
STATUS_URL = 'https://codex-resets.com/api/v1/status'
SITE_URL = 'https://codex-resets.com/'
ACCOUNT_NOTICE = '公开公告不代表你的账户额度已重置，请以本机账户读数为准。'
LABELS = {'reset': '第三方收录的重置公告', 'upcoming': '重置预告，尚未确认实施',
          'uncertain': '重置相关，尚待确认', 'update': '官方产品更新', 'other': '公开更新'}


def epoch(value):
    if isinstance(value, bool): return None
    try:
        if isinstance(value, (int, float)): stamp = float(value)
        else:
            date = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
            if date.tzinfo is None: return None
            stamp = date.timestamp()
        return stamp if math.isfinite(stamp) and 0 < stamp < 253402271999 else None
    except (ValueError, TypeError, OverflowError): return None


def interval(value):
    try:
        value = float(value)
        return max(5, min(1440, int(value))) if math.isfinite(value) else 15
    except (ValueError, TypeError, OverflowError): return 15


def safe_url(url, hosts, allow_fragment=False):
    try:
        parsed = urllib.parse.urlsplit(url)
        if (parsed.scheme != 'https' or parsed.hostname not in hosts or parsed.username
                or parsed.password or parsed.port not in (None, 443) or (parsed.fragment and not allow_fragment)):
            raise ValueError('unexpected URL origin')
    except (TypeError, ValueError): raise ValueError('unexpected URL origin') from None
    return url


def plain(value, maximum=MAX_TEXT):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError('invalid text')
    return ''.join(c for c in value if c in '\n\t' or ord(c) >= 32).strip()


def _pending_reset_kind(text):
    """Require explicit implementation language before allowing a reset sound.

    The third-party latest_reset field is a report, not proof that its text
    describes a completed action. Scope this guard to reset/limit sentences so
    "Done. See you tomorrow for good news" is not mistaken for a reset plan.
    This intentionally prefers a silent uncertain label to a false sound.
    """
    sentences = re.findall(r'[^.!?。！？;；\n]+[.!?。！？;；\n]*', text.lower().replace('’', "'"))
    relevant = re.compile(r'\b(?:reset\w*|quota\w*)\b|\b(?:rate|usage)\s+limits?\b|额度|重置')
    future = re.compile(
        r'\b(?:will|shall|gonna|soon|tomorrow|tonight|later|upcoming|planned|scheduled|planning)\b'
        r'|\b(?:going\s+to|plan\s+to|intend\s+to|expect\s+to|yet\s+to)\b'
        r'|\bin\s+(?:the\s+)?(?:next|an?|one|\d+)\s+(?:minutes?|hours?|days?|weeks?)\b'
        r'|\bend\s+of\s+(?:the\s+)?(?:day|week)\b|将会|将于|计划|预计|明天|稍后|即将')
    uncertain = re.compile(
        r"\b(?:if|unless|might|may|could|would|should|not|never|no|didn't|haven't|hasn't|isn't|aren't|wasn't|weren't|don't|doesn't|won't|cannot|can't)\b"
        r'|\b(?:imagine|suppose|hypothetical(?:ly)?|whether|rumou?r|every|each|daily|weekly|monthly)\b'
        r'|如果|假如|尚未|还未|没有|未曾')
    completed = re.compile(
        r"\b(?:we|i)(?:'ve|\s+have)?\s+(?:(?:just|now|already|fully|successfully)\s+)*reset\b"
        r"|\b(?:we(?:'re|\s+are)|i(?:'m|\s+am)|and\s+(?:are|am))\s+(?:now\s+)?reset(?:t)?ing\b"
        r"|\b(?:we|i)(?:'ve|\s+have)?\s+(?:now\s+)?(?:completed|applied|performed|finished)\s+(?:(?:a|the|full|rate|limit|usage|codex|chatgpt)\s+){0,6}reset\b"
        r'|\b(?:limits?|quotas?)\s+(?:(?:have|has)\s+(?:now\s+)?been|are|is|were|was)\s+(?:(?:now|fully|already|successfully|just)\s+)*reset\b'
        r'|\breset(?:\s+(?:is|was|has\s+been))?\s+(?:(?:now|fully|already)\s+)*(?:done|complete(?:d)?|applied|finished)\b')
    short_done = re.compile(r"^(?:and\s+)?(?:(?:it|that)(?:'s|\s+is)\s+)?(?:all\s+)?(?:done|completed)(?:\s+(?:now|today))?$")
    pending = None
    explicit_completion = False
    for index, sentence in enumerate(sentences):
        statement = sentence.strip().rstrip('.!?。！？;；').strip()
        question = '?' in sentence or '？' in sentence
        if not relevant.search(statement):
            # Only a short declarative Done is accepted from latest_reset's
            # explicit reset context. "Done with lunch" and "Done?" are not.
            if not question and short_done.fullmatch(statement): explicit_completion = True
            continue
        if question or uncertain.search(statement) or any(mark in statement for mark in ('"','“','”')):
            pending = 'uncertain'
            continue
        if future.search(statement):
            pending = pending or 'upcoming'
            continue
        if completed.search(statement): explicit_completion = True
        # A short timing continuation can refer back to the reset sentence.
        # Do not apply its time words to unrelated product/news sentences.
        if index + 1 < len(sentences):
            continuation = sentences[index + 1].strip()
            if (re.match(r'^(?:lands?|arriv(?:es?|ing)|goes?\s+live|starts?|propagating)\b', continuation)
                    and future.search(continuation)):
                pending = pending or 'upcoming'
    return pending or (None if explicit_completion else 'uncertain')


def retry_after(value, now=None):
    if value is None: return None
    now = time.time() if now is None else now
    try:
        delay = float(value)
    except (ValueError, TypeError):
        try:
            date = parsedate_to_datetime(str(value))
            if date.tzinfo is None: return None
            delay = date.timestamp() - now
        except (ValueError, TypeError, OverflowError): return None
    # Retry-After may legitimately be longer than our exponential backoff cap.
    return max(0, min(253402271998-now, delay)) if math.isfinite(delay) and delay >= 0 else None


class ProviderError(RuntimeError):
    def __init__(self, code, message, retry_after=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retry_after = retry_after


@dataclass
class FetchResult:
    items: list = field(default_factory=list)
    etag: str | None = None
    not_modified: bool = False


class _SameHostRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, host): self.host = host
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        try: safe_url(newurl, {self.host})
        except ValueError: raise ProviderError('redirect', '公告重定向来源不符，保留上次结果。') from None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _etag(value):
    return value if isinstance(value, str) and len(value) <= 512 and '\r' not in value and '\n' not in value else None


def fetch_bytes(url, *, host, etag=None, timeout=10, opener=None, accept='application/json', maximum=MAX_BYTES):
    """One bounded GET; normal system proxies/TLS only, no credential handlers.

    The injected opener is for offline tests. Redirects and final response URLs
    stay on the original fixed HTTPS host. The socket timeout is at most 15s.
    """
    safe_url(url, {host})
    timeout = max(1, min(15, float(timeout)))
    headers = {'Accept': accept, 'User-Agent': 'BailongDesktopPet-PublicAnnouncements/1',
               'Cache-Control': 'no-cache'}
    if _etag(etag): headers['If-None-Match'] = etag
    request = urllib.request.Request(url, headers=headers, method='GET')
    if opener is None:
        from tls_context import https_context
        opener = urllib.request.build_opener(_SameHostRedirect(host),
            urllib.request.HTTPSHandler(context=https_context())).open
    deadline=time.monotonic()+timeout
    try:
        with opener(request, timeout=timeout) as response:
            safe_url(response.geturl(), {host})
            status = getattr(response, 'status', 200)
            if status == 304: return None, _etag(response.headers.get('ETag')) or _etag(etag)
            if status != 200: raise ProviderError('http_'+str(status), '公告服务响应异常，保留上次结果。')
            length = response.headers.get('Content-Length')
            if length is not None:
                try:
                    if int(length) < 0 or int(length) > maximum: raise ValueError()
                except ValueError: raise ProviderError('response_size', '公告响应大小异常，保留上次结果。') from None
            # read1 performs at most one underlying read. Recheck the total
            # budget between chunks and tighten the standard HTTPResponse
            # socket timeout to the remaining budget, preventing a slow trickle
            # from monopolizing the worker and delaying the other source.
            chunks=[];received=0
            reader=getattr(response,'read1',response.read)
            while True:
                remaining=deadline-time.monotonic()
                if remaining<=0:raise ProviderError('timeout','公告读取超时，保留上次结果。')
                sock=getattr(getattr(getattr(response,'fp',None),'raw',None),'_sock',None)
                if sock is not None:sock.settimeout(remaining)
                block=reader(min(65536,maximum+1-received))
                if time.monotonic()>deadline:raise ProviderError('timeout','公告读取超时，保留上次结果。')
                if not block:break
                chunks.append(block);received+=len(block)
                if received>maximum:raise ProviderError('response_size','公告响应过大，保留上次结果。')
            raw=b''.join(chunks)
            if length is not None and len(raw) != int(length):
                raise ProviderError('incomplete_response', '公告响应不完整，保留上次结果。')
            return raw, _etag(response.headers.get('ETag'))
    except urllib.error.HTTPError as error:
        if error.code == 304: return None, _etag(error.headers.get('ETag')) or _etag(etag)
        raise ProviderError('http_'+str(error.code), '公告服务暂时不可用，保留上次结果。',
                            retry_after(error.headers.get('Retry-After'))) from None
    except ProviderError: raise
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        raise ProviderError('network', '公告连接或证书验证失败，保留上次结果。') from None


class CodexResetsProvider:
    id = 'codex_resets'
    label = 'Codex Resets（第三方）'
    attribution_url = SITE_URL
    available = True
    allowed_hosts = {'codex-resets.com'}
    def __init__(self, opener=None): self.opener = opener
    def fetch(self, *, etag=None, timeout=10):
        raw, response_etag = fetch_bytes(STATUS_URL, host='codex-resets.com', etag=etag,
                                       timeout=timeout, opener=self.opener)
        if raw is None: return FetchResult(etag=response_etag, not_modified=True)
        try: payload = json.loads(raw.decode('utf-8-sig'))
        except (ValueError, UnicodeError): raise ProviderError('schema', '第三方公告格式变化，保留上次结果。') from None
        return FetchResult(self.parse(payload), response_etag)

    def parse(self, payload):
        try:
            if not isinstance(payload, dict) or payload.get('meta', {}).get('api_version') != 'v1': raise ValueError()
            data = payload['data']
            if not isinstance(data, dict) or not {'latest_reset','scheduled_reset','active_watch'} <= data.keys(): raise ValueError()
            if data['active_watch'] is not None and not isinstance(data['active_watch'], dict): raise ValueError()
            items = []
            for key, kind in (('latest_reset','reset'), ('scheduled_reset','upcoming')):
                value = data[key]
                if value is None: continue
                if not isinstance(value, dict): raise ValueError()
                ident = plain(str(value['id']), 128)
                if not re.fullmatch(r'[1-9][0-9]{4,29}',ident):raise ValueError()
                published = epoch(value['announced_at'])
                if published is None: raise ValueError()
                reset_type = plain(value['reset_type'], 64)
                text = plain(value['text'])
                if key == 'latest_reset':
                    kind = _pending_reset_kind(text) or kind
                source = value['source']
                if not isinstance(source, dict) or source.get('type') != 'x_post': raise ValueError()
                author = plain(source['author'], 32).lstrip('@').lower()
                if author != 'thsottiaux': raise ValueError()
                origin = safe_url(source['url'], {'x.com'})
                parsed = urllib.parse.urlsplit(origin)
                if parsed.query or not re.fullmatch('/'+re.escape(author)+'/status/'+re.escape(ident)+r'/?', parsed.path, re.I): raise ValueError()
                item = dict(id=ident, text=text, summary=' '.join(text.split())[:180], published=published,
                    url=SITE_URL, origin_url=origin, source_author=author, kind=kind, label=LABELS[kind],
                    source_id=self.id, source_label=self.label, evidence_source='third_party', reset_type=reset_type,
                    implementation='reported_completed' if kind == 'reset' else 'scheduled' if key == 'scheduled_reset' else 'reported_unconfirmed')
                if kind == 'upcoming':
                    # Passing this time never changes the classification.
                    scheduled = value.get('scheduled_for')
                    if scheduled is not None and epoch(scheduled) is None: raise ValueError()
                    item['scheduled_for'] = epoch(scheduled)
                items.append(item)
            return items
        except (ValueError, TypeError, KeyError, AttributeError):
            raise ProviderError('schema', '第三方公告字段或引用来源无法核实，保留上次结果。') from None


class OfficialProductProvider:
    """Verified public Codex changelog RSS; content can never produce sound."""
    id = 'codex_changelog'
    label = 'Codex 官方更新'
    attribution_url = 'https://learn.chatgpt.com/docs/changelog'
    available = True
    allowed_hosts = {'learn.chatgpt.com', 'developers.openai.com'}
    url = 'https://learn.chatgpt.com/docs/changelog/rss.xml'
    def __init__(self, opener=None): self.opener = opener
    @staticmethod
    def validate_link(url):
        safe_url(url, OfficialProductProvider.allowed_hosts, allow_fragment=True)
        parsed=urllib.parse.urlsplit(url)
        allowed={'developers.openai.com':'/codex/changelog', 'learn.chatgpt.com':'/docs/changelog'}
        if parsed.path.rstrip('/')!=allowed[parsed.hostname] or parsed.query:
            raise ValueError('unexpected product link')
        return url
    def fetch(self, *, etag=None, timeout=10):
        raw,response_etag=fetch_bytes(self.url,host='learn.chatgpt.com',etag=etag,timeout=timeout,
            opener=self.opener,accept='application/rss+xml, application/xml',maximum=MAX_RSS_BYTES)
        if raw is None:return FetchResult(etag=response_etag,not_modified=True)
        return FetchResult(self.parse(raw),response_etag)
    def parse(self, raw):
        try:
            if not isinstance(raw,bytes) or len(raw)>MAX_RSS_BYTES:raise ValueError()
            xml=raw.decode('utf-8-sig')
            if '\x00' in xml or re.search(r'<!\s*(?:DOCTYPE|ENTITY)\b',xml,re.I):raise ValueError()
            root=ET.fromstring(xml)
            if root.tag!='rss' or root.get('version')!='2.0':raise ValueError()
            channels=root.findall('channel')
            if len(channels)!=1:raise ValueError()
            entries=channels[0].findall('item')
            if not entries or len(entries)>2000:raise ValueError()
            candidates=[]
            for entry in entries:
                title=plain(entry.findtext('title'),512)
                url=self.validate_link(entry.findtext('link'))
                guid=plain(entry.findtext('guid') or url,2048)
                date=parsedate_to_datetime(entry.findtext('pubDate'))
                if date.tzinfo is None:raise ValueError()
                published=epoch(date.timestamp())
                if published is None:raise ValueError()
                candidates.append((published,guid,title,url,entry))
            published,guid,title,url,entry=max(candidates,key=lambda value:(value[0],value[1]))
            html=entry.findtext('{http://purl.org/rss/1.0/modules/content/}encoded') or entry.findtext('description') or ''
            extractor=_PlainHTML();extractor.feed(html);extractor.close()
            body=' '.join(' '.join(extractor.parts).split())[:8000]
            text=title+('\n'+body if body else '')
            ident=guid if len(guid)<=128 else hashlib.sha256(guid.encode()).hexdigest()
            return [dict(id=ident,text=text,summary=' '.join(text.split())[:180],published=published,url=url,
                kind='update',label=LABELS['update'],source_id=self.id,source_label=self.label,
                evidence_source='official_changelog',coverage='官方变更日志，涵盖 Codex CLI、应用及 Work 等更新；不是个人推文。')]
        except (ValueError,TypeError,AttributeError,ET.ParseError,UnicodeError,OverflowError):
            raise ProviderError('schema','官方变更日志格式变化，保留上次结果。') from None


class _PlainHTML(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.parts=[];self.ignored=0
    def handle_starttag(self,tag,attrs):
        if tag.lower() in ('script','style'):self.ignored+=1
    def handle_endtag(self,tag):
        if tag.lower() in ('script','style') and self.ignored:self.ignored-=1
    def handle_data(self,data):
        if not self.ignored:self.parts.append(data)


def _atomic_json(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, path)


def _empty_state():
    return dict(initialized=False, seen=[], high_water=0, items=[], etag=None,
        checked=None, last_success=None, next_check=None, failures=0, state='unavailable',
        message='尚未检查此公开来源。', error_code=None)


class PublicAnnouncementMonitor:
    """One independent receipt/deadline per source; call from a background worker.

    Provider implementations are local trusted code, never selected by feed text.
    A single atomic cache contains separately keyed source states; old X and
    reset-watch files are never read. No timer is created by this class.
    """
    def __init__(self, path, providers=None, interval_minutes=15, sound_enabled=True, enabled=True):
        self.path = Path(path)
        self.providers = list(providers) if providers is not None else [CodexResetsProvider(), OfficialProductProvider()]
        ids = [provider.id for provider in self.providers]
        if len(ids) > 8 or len(set(ids)) != len(ids) or any(not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', ident) for ident in ids):
            raise ValueError('invalid provider ids')
        self.options = dict(interval_minutes=interval(interval_minutes), sound_enabled=bool(sound_enabled), enabled=bool(enabled))
        self.states = {ident: _empty_state() for ident in ids}
        self._lock = threading.RLock()
        self._poll_lock = threading.Lock()
        try:
            if self.path.stat().st_size > MAX_CACHE_BYTES: raise ValueError()
            saved = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(saved, dict) or saved.get('schema') != 1 or not isinstance(saved.get('sources'), dict): raise ValueError()
            for provider in self.providers:
                raw = saved['sources'].get(provider.id)
                try:
                    if not isinstance(raw, dict) or not isinstance(raw.get('initialized'), bool): raise ValueError()
                    if not isinstance(raw.get('seen'), list) or len(raw['seen']) > 512 or any(not isinstance(i, str) or len(i)>256 for i in raw['seen']): raise ValueError()
                    if not isinstance(raw.get('items'), list) or len(raw['items']) > 1: raise ValueError()
                    if not isinstance(raw.get('failures'), int) or not 0<=raw['failures']<=16: raise ValueError()
                    if not isinstance(raw.get('high_water'), (int,float)) or not math.isfinite(raw['high_water']) or raw['high_water']<0: raise ValueError()
                    for key in ('checked','last_success','next_check'):
                        if raw.get(key) is not None and epoch(raw[key]) is None: raise ValueError()
                    checked_items=self._validate_items(provider, raw['items'])
                    self.states[provider.id] = dict(_empty_state(), **raw)
                    self.states[provider.id]['etag']=_etag(raw.get('etag'))
                    self.states[provider.id]['items']=checked_items
                except (ValueError, TypeError, KeyError):
                    pass  # Only this source establishes a fresh silent baseline.
        except (OSError, ValueError, TypeError): pass

    def configure(self, *, interval_minutes=None, sound_enabled=None, enabled=None):
        with self._lock:
            if interval_minutes is not None: self.options['interval_minutes'] = interval(interval_minutes)
            if sound_enabled is not None: self.options['sound_enabled'] = bool(sound_enabled)
            if enabled is not None:
                if enabled and not self.options['enabled']:
                    for state in self.states.values(): state.update(initialized=False, next_check=None, etag=None)
                self.options['enabled'] = bool(enabled)

    def _validate_items(self, provider, items):
        if not isinstance(items, list) or len(items)>MAX_ITEMS: raise ValueError('item limit')
        output=[]
        for raw in items:
            if not isinstance(raw, dict): raise ValueError('item schema')
            kept=('id','text','published','url','kind','origin_url','source_author','evidence_source',
                  'reset_type','implementation','scheduled_for','coverage')
            item={key:raw[key] for key in kept if key in raw}
            item['id']=plain(item.get('id'),128)
            item['text']=plain(item.get('text'))
            item['published']=epoch(item.get('published'))
            if item['published'] is None or item.get('kind') not in LABELS: raise ValueError('item time/kind')
            safe_url(item.get('url'), provider.allowed_hosts, allow_fragment=True)
            if hasattr(provider,'validate_link'):provider.validate_link(item['url'])
            for key in ('source_author','evidence_source','reset_type','implementation','coverage'):
                if key in item:item[key]=plain(item[key],512)
            if 'origin_url' in item:
                safe_url(item['origin_url'],{'x.com'})
                parsed=urllib.parse.urlsplit(item['origin_url'])
                if parsed.query or not re.fullmatch(r'/thsottiaux/status/[1-9]\d{4,29}/?',parsed.path,re.I):raise ValueError('origin link')
            if item.get('scheduled_for') is not None and epoch(item['scheduled_for']) is None:raise ValueError('schedule')
            item.update(source_id=provider.id, source_label=provider.label,
                summary=' '.join(item['text'].split())[:180], label=LABELS[item['kind']])
            output.append(item)
        return output

    def snapshot(self, now=None):
        now = time.time() if now is None else now
        with self._lock:
            sources=[]
            for provider in self.providers:
                stored=self.states[provider.id]
                status=stored['state']
                if not self.options['enabled']: status='disabled'
                elif not provider.available: status='unavailable'
                last=stored['last_success']
                sources.append(dict(id=provider.id,label=provider.label,attribution_url=provider.attribution_url,
                    state=status,message=('此来源已关闭。' if status=='disabled' else '此公开来源尚未接通，当前不发送请求。' if not provider.available else stored['message']),
                    error_code=stored.get('error_code'),checked=stored['checked'],last_success=last,
                    next_check=stored['next_check'] if self.options['enabled'] and provider.available else None,
                    stale=last is None or status!='ok' or now-last>self.options['interval_minutes']*120,
                    items=copy.deepcopy(stored['items'])))
            statuses=[s['state'] for s in sources]
            state='disabled' if not self.options['enabled'] else 'ok' if statuses and all(s=='ok' for s in statuses) else 'degraded' if 'ok' in statuses else 'error'
            latest=lambda key: max([s[key] for s in sources if s[key] is not None],default=None)
            return dict(source='public_announcements',sources=sources,state=state,
                message={'ok':'公开来源已更新。','degraded':'部分来源暂时不可用，保留各自上次结果。','error':'公开来源暂时不可用，保留上次结果。','disabled':'公开更新检查已关闭。'}[state],
                checked=latest('checked'),last_success=latest('last_success'),
                next_check=min([s['next_check'] for s in sources if s['next_check'] is not None],default=None),
                stale=any(s['stale'] for s in sources),items=[],account_notice=ACCOUNT_NOTICE,**self.options)

    def _persist(self): _atomic_json(self.path, dict(schema=1,sources=self.states))

    def _error(self, provider, code, message, now, retry=None):
        state=self.states[provider.id]
        failures=min(16,state['failures']+1)
        delay=min(MAX_BACKOFF,self.options['interval_minutes']*60*2**(failures-1))
        delay=max(delay,retry_after(retry,now) or 0)
        state.update(state='error',error_code=code,message=message,checked=now,failures=failures,next_check=now+delay)
        try:self._persist()
        except OSError:pass

    def poll(self, now=None, force=False):
        now=time.time() if now is None else epoch(now)
        if now is None: raise ValueError('invalid time')
        if not self._poll_lock.acquire(blocking=False): return self.snapshot(now),[]
        alerts=[]
        try:
            for provider in self.providers:
                with self._lock:
                    if not self.options['enabled']: break
                    if not provider.available: continue
                    state=self.states[provider.id]
                    if state['next_check'] and now<state['next_check'] and (not force or state['failures']): continue
                    etag=state['etag']
                try:
                    result=provider.fetch(etag=etag,timeout=10)
                    if not isinstance(result,FetchResult): raise ValueError('provider result')
                    with self._lock:
                        old=copy.deepcopy(self.states[provider.id])
                        if result.not_modified:
                            if not old['initialized'] or old['last_success'] is None:
                                raise ProviderError('invalid_304','来源返回 304，但本机没有可重用的缓存。')
                            items=old['items']
                        else:items=self._validate_items(provider,result.items)
                        current=[]
                        for item in items:
                            if item['published']>now:
                                item.update(kind='uncertain',label=LABELS['uncertain'])
                            current.append(item)
                        # A valid empty status does not erase the last published
                        # entry. Schema errors never reach this path.
                        merged={i['id']:i for i in old['items']}
                        merged.update({i['id']:i for i in current})
                        shown=sorted(merged.values(),key=lambda i:(i['published'],i['id']),reverse=True)[:1]
                        # A corrupt future confirmed timestamp is seen but never
                        # promoted to a sound merely because time later passes.
                        receipts=[i['id']+':'+i['kind'] for i in current]
                        receipts.extend(i['id']+':reset' for i in current if i.get('implementation')=='reported_completed' and i['published']>now)
                        baseline=max(old['high_water'],old['last_success'] or 0)
                        new=[i for i in current if i['kind']=='reset' and provider.id=='codex_resets'
                             and i['id']+':reset' not in old['seen'] and i['published']>=baseline and i['published']>old['high_water']
                             and i.get('implementation')=='reported_completed']
                        candidate=dict(old,initialized=True,items=shown,seen=list(dict.fromkeys(receipts+old['seen']))[:512],
                            high_water=max([old['high_water']]+[i['published'] for i in current if i['published']<=now]),
                            etag=_etag(result.etag) if not result.not_modified else _etag(result.etag) or old['etag'],
                            checked=now,last_success=now,next_check=now+self.options['interval_minutes']*60,
                            failures=0,state='ok',message='已完成公开来源重验证。' if result.not_modified else '已取得此来源的公开更新。',error_code=None)
                        self.states[provider.id]=candidate
                        try:self._persist()
                        except OSError:
                            # Keep displayed data but never move successful-check
                            # time or issue sound without durable receipts.
                            candidate['last_success']=old['last_success']
                            self._error(provider,'cache_write','公告缓存保存失败，本次保持静音。',now)
                            continue
                        if old['initialized'] and not result.not_modified and self.options['enabled'] and self.options['sound_enabled']:
                            alerts.extend(dict(id=i['id'],kind='reset',source_id=provider.id,title='第三方收录了新的额度重置公告',text=i['summary'],url=i['url'])
                                          for i in {i['id']:i for i in new}.values())
                except ProviderError as error:
                    with self._lock:self._error(provider,error.code,error.message,now,error.retry_after)
                except (ValueError,TypeError,KeyError):
                    with self._lock:self._error(provider,'schema','公告格式变化，保留该来源上次结果。',now)
                except Exception:
                    with self._lock:self._error(provider,'network','公告查询失败，保留该来源上次结果。',now)
            return self.snapshot(now),alerts
        finally:self._poll_lock.release()
