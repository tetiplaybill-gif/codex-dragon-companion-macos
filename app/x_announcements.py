"""Bounded, credential-free announcement state machine for @thsottiaux.

No network implementation is enabled. Free automatic reading is not connected;
the official X page can be opened for normal login. A provider may be injected
only after a permitted and reliable free source is arranged. Public
post text is display data, never instructions, HTML, code or account evidence.
"""
import copy
import json
import math
import os
import re
import threading
import time
from datetime import datetime
from pathlib import Path

ACCOUNT = 'thsottiaux'
SOURCE_URL = 'https://x.com/thsottiaux'
ACCOUNT_NOTICE = '公开公告不代表你的账户额度已重置，请以本机账户读数为准。'
MAX_POSTS = 100
MAX_ITEMS = 1
MAX_TEXT = 25000
MAX_CACHE_BYTES = 2 * 1024 * 1024
DEFAULT_INTERVAL_MINUTES = 15
MAX_BACKOFF = 24 * 3600
KIND_LABELS = {'reset': '额度重置公告', 'upcoming': '未来预告，尚未确认实施',
               'uncertain': '重置相关，尚待确认', 'update': '产品与功能更新',
               'other': '最新推文'}


class SourceUnavailable(RuntimeError):
    code = 'free_source_unavailable'


class UnavailableProvider:
    """Explicitly offline; never uses login cookies, proxies or the old feed."""
    available = False
    def fetch(self, *, since_id=None, limit=MAX_POSTS, timeout=10):
        raise SourceUnavailable('免费自动读取尚未接通；可在 X 官方页面登录查看。')


def interval_minutes(value):
    try:
        value = float(value)
        if not math.isfinite(value): raise ValueError()
        return max(5, min(1440, int(value)))
    except (ValueError, TypeError, OverflowError):
        return DEFAULT_INTERVAL_MINUTES


def timestamp(value):
    if isinstance(value, bool): return None
    try:
        if isinstance(value, (int, float)):
            result = float(value)
        else:
            date = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
            if date.tzinfo is None: return None
            result = date.timestamp()
        return result if math.isfinite(result) and 0 < result < 253402271999 else None
    except (TypeError, ValueError, OverflowError):
        return None


def _text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_TEXT:
        raise ValueError('invalid post text')
    # Preserve the original content and newlines; remove only control codes.
    return ''.join(c for c in value if c in '\n\t' or ord(c) >= 32).strip()


def _search_text(text):
    # A link's slug is not evidence of what the author announced.
    return re.sub(r'https?://\S+', '', text).lower().replace('’', "'")


_PRODUCT = re.compile(r'\b(?:codex|chatgpt)\b', re.I)
_QUOTA = re.compile(r'\b(?:rate[ -]?limits?|usage[ -]?limits?|limits?|quotas?|credits?)\b|额度|限额', re.I)
_RESET = re.compile(r'\breset(?:s|ting)?\b|重置|重设', re.I)
_FUTURE = re.compile(r"\b(?:will|tomorrow|tonight|soon|planned|planning|scheduled|next\s+\w+|going to|expect(?:ed|ing)?|hope(?:fully)?|might|may|could|would|should|in\s+(?:a|an|one|two|three|four|five|six|\d+)\s+(?:minutes?|hours?|days?|weeks?)|on\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b|将(?:会|于)?|预计|计划|明天|稍后|即将", re.I)
_NEGATION = re.compile(r"\b(?:not|never|no|didn't|don't|doesn't|haven't|hasn't|isn't|aren't|wasn't|won't|cannot|can't|incorrect|false|rumou?r)\b|没有|尚未|未曾|不会|并非|误报|谣言", re.I)
_HISTORICAL = re.compile(r'\b(?:yesterday|last week|last month|previously|used to|earlier this year)\b|昨天|上周|上个月|曾经|去年', re.I)
_CONDITIONAL = re.compile(r'\b(?:if|unless|whenever|every|usually|normally|typically|imagine|suppose|whether|hourly|daily|weekly|monthly|yearly|regularly)\b|如果|假如|每隔|通常|一般会|每天|每周|每月', re.I)
_QUOTED = re.compile(r'\b(?:said|says|claimed|claims|according to|quoting|reportedly|quote|wrote|writes|saying|told|example|sample|draft|hypothetical)\b|["“”>]|(?:^|\s)\x27we\b|据说|声称|引用|例如|示例|草稿', re.I)
_DONE = re.compile(r"(?:done(?: now)?|it's done|all done|已完成|已重置)[.!。！\s]*", re.I)
_UPDATE = re.compile(r'\b(?:launch(?:ed|ing)?|releas(?:e|ed|ing)|ship(?:ped|ping)?|roll(?:ing|ed)? out|available|introduc(?:e|ed|ing)|new|improv(?:e|ed|ement|ements)|updat(?:e|ed|es)|support(?:s|ed)?|fix(?:ed|es)?)\b|发布|上线|新增|推出|更新|支持|改进|修复', re.I)


def classify(text):
    """High precision rules; missing context and ambiguous timing stay silent."""
    value = _search_text(text)
    if not _PRODUCT.search(value): return None
    reset = bool(_RESET.search(value) and _QUOTA.search(value))
    if reset:
        # "weekly limits" names a quota; "reset limits weekly" is a policy.
        timing = re.sub(r'\b(?:hourly|daily|weekly|monthly|yearly)(?=\s+(?:(?:codex|chatgpt)\s+)?(?:(?:usage|rate)\s+)?(?:limits?|quotas?|credits?)\b)', '', value)
        if _NEGATION.search(value) or _CONDITIONAL.search(timing) or _QUOTED.search(value) or '?' in value or '？' in value:
            return 'uncertain'
        if _FUTURE.search(value): return 'upcoming'
        if _HISTORICAL.search(value): return 'uncertain'
        # Require a declarative actor or passive quota subject in the same
        # sentence as the product. Imperatives ("Reset ... now"), instructions
        # ("You can reset ...") and quoted claims must never ring.
        completed = False
        for sentence in re.split(r'[.!?;\n。！？；]+', value):
            sentence = sentence.strip()
            if not (_PRODUCT.search(sentence) and _QUOTA.search(sentence)):
                continue
            active = re.match(r"(?:we(?:'ve| have)\s+(?:just\s+)?|we\s+just\s+)reset\b", sentence)
            ongoing = re.match(r"we(?:'re| are)\s+(?:now\s+)?resetting\b", sentence) and re.search(r'\bnow\b', sentence)
            passive = (re.match(r'(?:all\s+|your\s+|the\s+)?(?:codex|chatgpt|rate[ -]?limits?|usage[ -]?limits?|limits?|quotas?|credits?)\b', sentence)
                       and re.search(r'\b(?:limits?|quotas?|credits?)\b[^.!?\n]{0,80}\b(?:have been|has been|were|was|are now|is now)\s+(?:fully\s+)?reset\b', sentence))
            chinese = ((sentence.startswith('我们') or re.match(r'(?:codex|chatgpt)\b', sentence))
                       and re.search(r'(?:已|已经|刚刚)(?:为[^。！？\n]{0,30})?重置|重置(?:已完成|完成了)', sentence))
            completed |= bool(active or ongoing or passive or chinese)
        return 'reset' if completed else 'uncertain'
    return 'update' if _UPDATE.search(value) else None


def normalize_post(raw, *, allow_parent=True):
    """Require an explicitly resolved author; never trust a supplied URL."""
    if not isinstance(raw, dict): raise ValueError('invalid post')
    author = raw.get('author') or raw.get('username')
    if not isinstance(author, str) or author.lstrip('@').lower() != ACCOUNT:
        raise ValueError('unexpected post author')
    ident = str(raw.get('id', ''))
    if not re.fullmatch(r'[1-9]\d{4,29}', ident): raise ValueError('invalid post id')
    published = timestamp(raw.get('created_at', raw.get('published')))
    if published is None: raise ValueError('invalid post date')
    text = _text(raw.get('text'))
    references = raw.get('referenced_tweets', [])
    if not isinstance(references, list): raise ValueError('invalid references')
    # Retweets belong to someone else. Quoted claims alone cannot establish a reset.
    if any(isinstance(r, dict) and r.get('type') == 'retweeted' for r in references):
        return None
    kind = classify(text)
    context = None
    if allow_parent and _DONE.fullmatch(_search_text(text).strip()) and isinstance(raw.get('parent'), dict):
        parent = normalize_post(raw['parent'], allow_parent=False)
        parent_id = str(raw.get('in_reply_to_id', ''))
        matching_reference = any(isinstance(r, dict) and r.get('type') == 'replied_to' and str(r.get('id')) == parent_id for r in references)
        if (parent and parent['id'] == parent_id and matching_reference
                and parent['published'] < published and parent['kind'] == 'upcoming'
                and re.search(r"\b(?:we will|we're going to|we are going to|we plan to)\s+reset\b|我们(?:将|计划)重置", _search_text(parent['text']))):
            kind = 'reset'
            context = parent
    # Latest-only includes ordinary authored posts, with no sound. Retweets of
    # someone else's content were excluded above.
    if kind is None: kind = 'other'
    result = dict(id=ident, text=text, summary=' '.join(text.split())[:180],
                  published=published, url=f'{SOURCE_URL}/status/{ident}',
                  kind=kind, label=KIND_LABELS[kind])
    if context:
        result.update(context_text=context['text'], context_url=context['url'], context_published=context['published'])
    return result


def parse_official_response(payload):
    """Parse an authorized official API response, with author expansion required.

    This is a pure parser and performs no API call. Provider must resolve the
    target user's identity via official access; it cannot label arbitrary data.
    """
    if not isinstance(payload, dict) or payload.get('errors'):
        raise ValueError('incomplete official response')
    data = payload.get('data', [])
    if not isinstance(data, list) or len(data) > MAX_POSTS: raise ValueError('too many posts')
    users = (payload.get('includes') or {}).get('users', [])
    if not isinstance(users, list) or len(users) > 100: raise ValueError('invalid authors')
    authors = {str(u.get('id')): u.get('username') for u in users if isinstance(u, dict)}
    posts = []
    for raw in data:
        if not isinstance(raw, dict): raise ValueError('invalid post')
        author = authors.get(str(raw.get('author_id')))
        if not isinstance(author, str) or author.lower() != ACCOUNT: raise ValueError('author not resolved')
        note = raw.get('note_tweet')
        if note is not None and (not isinstance(note, dict) or not isinstance(note.get('text'), str)):
            raise ValueError('invalid full post text')
        posts.append(dict(raw, author=author, text=note['text'] if note is not None else raw.get('text')))
    return posts


def _atomic_json(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, path)


class AnnouncementMonitor:
    """Call poll from a background worker; no timer/thread is created here.

    Persist the receipt before returning sound events. Batch notifications should
    play at most one sound. A failed write suppresses audio to prevent repeats.
    Provider fetch must honor timeout=10, limit=100 and return a bounded list.
    """
    def __init__(self, path, provider=None, interval_minutes=15, sound_enabled=True, enabled=True):
        self.path = Path(path)
        self.provider = provider if provider is not None else UnavailableProvider()
        self._lock = threading.RLock()
        self._poll_lock = threading.Lock()
        self.options = {'interval_minutes': globals()['interval_minutes'](interval_minutes),
                        'sound_enabled': bool(sound_enabled), 'enabled': bool(enabled)}
        self.state = {'schema': 1, 'initialized': False, 'seen': [], 'items': [],
                      'high_water': '0', 'failures': 0, 'last_success': None,
                      'checked': None, 'next_check': None}
        try:
            if self.path.stat().st_size > MAX_CACHE_BYTES: raise ValueError('cache too large')
            saved = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(saved, dict) or saved.get('schema') != 1: raise ValueError('schema')
            if not isinstance(saved.get('seen'), list) or len(saved['seen']) > 512: raise ValueError('seen')
            if any(not isinstance(i, str) or not re.fullmatch(r'[1-9]\d{4,29}', i) for i in saved['seen']): raise ValueError('seen id')
            if not re.fullmatch(r'\d{1,30}', str(saved.get('high_water', ''))): raise ValueError('watermark')
            if not isinstance(saved.get('initialized'), bool): raise ValueError('initialized')
            if not isinstance(saved.get('failures', 0), int) or not 0 <= saved.get('failures', 0) <= 16: raise ValueError('failures')
            for key in ('last_success', 'checked', 'next_check', 'last_manual_read'):
                if saved.get(key) is not None and timestamp(saved[key]) is None: raise ValueError('cache timestamp')
            items = saved.get('items', [])
            # Accept the previous bounded cache shape, preserving receipts while
            # collapsing the display to the newest authored post by publication.
            if not isinstance(items, list) or len(items) > 50: raise ValueError('items')
            # Restore only normalized local display data, with canonical links.
            checked_items = []
            for item in items:
                raw = dict(item, author=ACCOUNT)
                context_id = re.fullmatch(re.escape(SOURCE_URL) + r'/status/([1-9]\d{4,29})', str(item.get('context_url', '')))
                if context_id:
                    ident = context_id[1]
                    raw.update(parent=dict(id=ident, author=ACCOUNT, text=item.get('context_text'), published=item.get('context_published')),
                               in_reply_to_id=ident, referenced_tweets=[dict(type='replied_to', id=ident)])
                original_kind = item.get('kind')
                item = normalize_post(raw)
                if item and original_kind == 'uncertain' and item['kind'] == 'reset':
                    item.update(kind='uncertain', label=KIND_LABELS['uncertain'])
                if item: checked_items.append(item)
            saved['items'] = sorted(checked_items, key=lambda item: (item['published'], int(item['id'])), reverse=True)[:MAX_ITEMS]
            self.state.update(saved)
        except (OSError, ValueError, TypeError, KeyError):
            pass  # A corrupt/missing receipt establishes a silent new baseline.

    def configure(self, *, interval_minutes=None, sound_enabled=None, enabled=None):
        with self._lock:
            if interval_minutes is not None:
                self.options['interval_minutes'] = globals()['interval_minutes'](interval_minutes)
            if sound_enabled is not None: self.options['sound_enabled'] = bool(sound_enabled)
            if enabled is not None:
                if enabled and not self.options['enabled']:
                    self.state['initialized'] = False  # re-enable without a historical chorus
                    self.state['next_check'] = None
                self.options['enabled'] = bool(enabled)

    def snapshot(self, now=None):
        now = time.time() if now is None else now
        with self._lock:
            last = self.state.get('last_success')
            status = self.state.get('status', 'unconfigured')
            if not self.options['enabled']: status = 'disabled'
            elif not getattr(self.provider, 'available', True): status = 'unconfigured'
            message = {'unconfigured': '免费自动读取尚未接通；可在 X 官方页面登录查看。',
                       'disabled': '自动检查已关闭；保留已取得的公告。',
                       'ok': '已读取 @thsottiaux 的公开公告。'}.get(status, self.state.get('message', '读取失败，保留上次公告。'))
            return dict(source='x', account=ACCOUNT, source_url=SOURCE_URL,
                state=status, message=message,
                error_code='free_source_unavailable' if status == 'unconfigured' else self.state.get('error_code'),
                checked=self.state.get('checked'), last_success=last,
                last_manual_read=self.state.get('last_manual_read'),
                display_origin=self.state.get('display_origin'),
                next_check=None if status in ('unconfigured', 'disabled') else self.state.get('next_check'),
                stale=last is None or status != 'ok' or now - last > self.options['interval_minutes'] * 120,
                items=copy.deepcopy(self.state['items']), account_notice=ACCOUNT_NOTICE, **self.options)

    def record_visible_post(self, raw, observed_at=None):
        """Record one externally verified, visible official-page post, silently.

        The caller must have read the normal official page; this method does not
        browse, log in, verify the observation itself, or enable a provider. It
        returns (snapshot, []), preserves automatic last_success/checked fields,
        and raises on a failed durable write without claiming a saved result.
        """
        now = time.time() if observed_at is None else timestamp(observed_at)
        if now is None: raise ValueError('invalid observation time')
        item = normalize_post(raw)
        if item is None: raise ValueError('only authored visible posts may be recorded')
        if item['published'] > now + 300:
            item.update(kind='uncertain', label=KIND_LABELS['uncertain'])
        with self._lock:
            candidate = copy.deepcopy(self.state)
            combined = {old['id']: old for old in candidate['items']}
            combined[item['id']] = item
            candidate['items'] = sorted(combined.values(), key=lambda old: (old['published'], int(old['id'])), reverse=True)[:MAX_ITEMS]
            candidate.update(initialized=True, last_manual_read=now,
                seen=list(dict.fromkeys([item['id']] + candidate['seen']))[:512],
                high_water=str(max(int(candidate['high_water']), int(item['id']))))
            if candidate['items'][0]['id'] == item['id']:
                candidate['display_origin'] = 'official_visible_page'
            _atomic_json(self.path, candidate)
            self.state = candidate
            return self.snapshot(now), []

    def poll(self, now=None, force=False):
        now = time.time() if now is None else float(now)
        if not math.isfinite(now) or now <= 0: raise ValueError('invalid current time')
        if not self._poll_lock.acquire(blocking=False): return self.snapshot(now), []
        try:
            with self._lock:
                if not self.options['enabled'] or not getattr(self.provider, 'available', True):
                    return self.snapshot(now), []
                due = self.state.get('next_check') or 0
                # Explicit refresh can skip ordinary cadence, but not an error backoff.
                if now < due and (not force or self.state.get('failures', 0)):
                    return self.snapshot(now), []
                since = self.state.get('high_water')
            try:
                raw_posts = self.provider.fetch(since_id=since if since != '0' else None, limit=MAX_POSTS, timeout=10)
                if not isinstance(raw_posts, list) or len(raw_posts) > MAX_POSTS: raise ValueError('response size')
                items = []
                raw_ids = []
                for raw in raw_posts:
                    item = normalize_post(raw)
                    raw_ids.append(str(raw['id']))
                    # A future timestamp may be a bad clock or malformed data; never beep.
                    if item and item['published'] > now + 300: item.update(kind='uncertain', label=KIND_LABELS['uncertain'])
                    if item: items.append(item)
                return self._success(items, raw_ids, now)
            except SourceUnavailable:
                return self._failure('free_source_unavailable', '免费自动读取尚未接通；可在 X 官方页面登录查看。', now)
            except (ValueError, TypeError, KeyError):
                return self._failure('invalid_response', '公告格式或作者无法核实，保留上次公告。', now)
            except Exception:
                # Do not reflect exception text (could include request headers/tokens).
                return self._failure('network', 'X 公告读取失败，保留上次结果；稍后重试。', now)
        finally:
            self._poll_lock.release()

    def _success(self, items, raw_ids, now):
        with self._lock:
            old = self.state
            watermark = int(old['high_water'])
            merged = {item['id']: item for item in old['items']}
            merged.update({item['id']: item for item in items})
            ordered = sorted(merged.values(), key=lambda item: (item['published'], int(item['id'])), reverse=True)[:MAX_ITEMS]
            seen = list(dict.fromkeys(sorted(raw_ids, key=int, reverse=True) + old['seen']))[:512]
            baseline_time = max(old.get('last_success') or 0, old.get('last_manual_read') or 0)
            new = [item for item in items if item['kind'] == 'reset' and int(item['id']) > watermark and item['id'] not in old['seen']
                   and item['published'] >= baseline_time]
            alerts = []
            if old.get('initialized') and self.options['sound_enabled'] and self.options['enabled']:
                # Deduplicate within a response as well as across polls/restarts.
                alerts = [dict(id=item['id'], title=KIND_LABELS['reset'], text=item['summary'], url=item['url'])
                          for item in {i['id']: i for i in new}.values()]
            self.state = dict(schema=1, initialized=True, items=ordered, seen=seen,
                high_water=str(max([watermark] + [int(i) for i in raw_ids])), failures=0,
                checked=now, last_success=now, next_check=now+self.options['interval_minutes']*60,
                status='ok', message='', error_code=None,
                last_manual_read=old.get('last_manual_read'),
                display_origin='automatic_provider' if ordered and ordered[0]['id'] in {i['id'] for i in items} else old.get('display_origin'))
            # Rare long-form posts may each contain 25,000 Unicode characters.
            # Keep the newest display entries within the same bound as loading;
            # durable IDs/high-water remain independent of display retention.
            while self.state['items'] and len(json.dumps(self.state, ensure_ascii=False).encode('utf-8')) > MAX_CACHE_BYTES-4096:
                self.state['items'].pop()
            try: _atomic_json(self.path, self.state)
            except OSError:
                return self._failure('cache_write', '已取得公告，但去重记录保存失败；本次保持静音。', now)
            return self.snapshot(now), alerts

    def _failure(self, code, message, now):
        with self._lock:
            failures = min(16, self.state.get('failures', 0) + 1)
            self.state.update(status='unconfigured' if code == 'free_source_unavailable' else 'error',
                error_code=code, message=message, checked=now, failures=failures,
                next_check=now+min(MAX_BACKOFF, self.options['interval_minutes']*60*(2**(failures-1))))
            try: _atomic_json(self.path, self.state)
            except OSError: pass
            return self.snapshot(now), []
