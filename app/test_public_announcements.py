"""Offline public-source contract tests. No network, user state or audio."""
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch
from email.utils import formatdate

import public_announcements as p

NOW=1793255000.


def item(ident='10001',published=NOW-1,kind='reset',**extra):
    return dict(id=ident,text='A public update.',published=published,kind=kind,
                url=p.SITE_URL,implementation='reported_completed' if kind=='reset' else 'scheduled',**extra)


def record(ident='10001',published=NOW-1):
    return dict(id=ident,reset_type='regular',announced_at=published,text='And it is done.',
                source=dict(type='x_post',author='thsottiaux',url='https://x.com/thsottiaux/status/'+ident))


def payload(latest=None,scheduled=None):
    return dict(meta={'api_version':'v1'},data={'latest_reset':latest,'scheduled_reset':scheduled,'active_watch':None})


class FakeProvider:
    available=True
    allowed_hosts={'codex-resets.com'}
    attribution_url=p.SITE_URL
    def __init__(self,ident='codex_resets'):
        self.id=ident;self.label=ident;self.calls=[];self.result=p.FetchResult([item()], '"one"');self.error=None
    def fetch(self,**kwargs):
        self.calls.append(kwargs)
        if self.error:raise self.error
        return self.result


class Response(io.BytesIO):
    status=200
    def __init__(self,raw,url=p.STATUS_URL,headers=None):
        super().__init__(raw);self.url=url;self.headers=headers or {}
    def geturl(self):return self.url


class ProviderTests(unittest.TestCase):
    def test_v1_payload_preserves_reported_origin_and_schedules(self):
        data=payload(record(),dict(record('10002'),scheduled_for=NOW+900))
        values=p.CodexResetsProvider().parse(data)
        self.assertEqual([v['kind'] for v in values],['reset','upcoming'])
        self.assertEqual(values[0]['origin_url'],'https://x.com/thsottiaux/status/10001')
        self.assertEqual(values[0]['source_author'],'thsottiaux')
        self.assertEqual(values[0]['evidence_source'],'third_party')
        self.assertEqual(values[0]['url'],p.SITE_URL)

    def test_invalid_schema_never_silently_becomes_empty(self):
        wrong=[{}, {'meta':{'api_version':'v2'},'data':{}},payload(dict(record(),source={})),
               payload(dict(record(),id='changed-id-but-same-old-url')),payload(dict(record(),id='10002')),
               payload(dict(record(),announced_at='invalid')), payload(dict(record(),source=dict(type='x_post',author='other',url='https://x.com/other/status/10001')))]
        for data in wrong:
            with self.subTest(data=data),self.assertRaises(p.ProviderError):p.CodexResetsProvider().parse(data)
        self.assertEqual(p.CodexResetsProvider().parse(payload()),[])

    def test_latest_reset_field_does_not_override_real_future_announcement_text(self):
        examples = [
            'Codex usage limits will be fully reset again in the next hour and we will credit one additional reset into your bank for your own usage over the next 24 hours.',
            "Codex is back up. Team will reset rate limits, that's been a while. Enjoy one on us.",
            'We will do the full banked reset today too for all Plus, Pro and Business users. Lands end of day.',
            'Enjoy a full reset of your usage limits for ChatGPT Work and Codex. Propagating in the next hour.',
            'A full Codex reset. Lands end of day.',
        ]
        fixture=Path(__file__).resolve().parents[2]/'verification/public-sources/codex-resets-live.json'
        if fixture.is_file():
            saved=json.loads(fixture.read_text())
            events=saved.get('events',[]) if isinstance(saved,dict) else []
            examples.extend(value['text'] for value in events if value.get('tweet_id') in
                            ('2071740419030053227','2028649088594436225'))
        for text in examples:
            with self.subTest(text=text):
                result=p.CodexResetsProvider().parse(payload(dict(record(),text=text)))[0]
                self.assertEqual(result['kind'],'upcoming')
                self.assertEqual(result['implementation'],'reported_unconfirmed')
                self.assertEqual(result['text'],text)
        conditional=p.CodexResetsProvider().parse(payload(dict(record(),text='If needed, we could reset Codex limits.')))[0]
        self.assertEqual(conditional['kind'],'uncertain')

    def test_unrelated_future_good_news_does_not_change_done_report(self):
        text="And it's done. See you tomorrow for some good news. https://t.co/WhJle2cWRG"
        result=p.CodexResetsProvider().parse(payload(dict(record(),text=text)))[0]
        self.assertEqual(result['kind'],'reset')
        self.assertEqual(result['implementation'],'reported_completed')

    def test_negative_question_and_hypothetical_reset_reports_are_uncertain(self):
        examples = [
            'We have not reset Codex limits yet.', 'The Codex reset is not done.',
            'We did not reset rate limits.', "We haven't reset Codex limits.",
            'No Codex reset is done.', 'We never reset Codex limits.',
            'Have Codex limits been reset?', 'Did we reset Codex limits?',
            'Is it reset?', 'Suppose we reset Codex limits.',
            'If needed, we have reset Codex limits.', 'We reset Codex limits every week.',
            'Reset Codex limits now.', 'You can reset your Codex limits now.',
            'There is a Codex reset.', 'A public update.', 'Done?', 'Done with lunch.',
            'Someone said "we reset Codex limits".',
        ]
        for text in examples:
            with self.subTest(text=text):
                result=p.CodexResetsProvider().parse(payload(dict(record(),text=text)))[0]
                self.assertEqual(result['kind'],'uncertain')
                self.assertEqual(result['implementation'],'reported_unconfirmed')
                self.assertEqual(result['text'],text)

    def test_explicit_implementation_and_contextual_done_are_required(self):
        examples = [
            'We have reset Codex usage limits.', 'I have now reset Codex limits.',
            'Codex usage limits have been fully reset.', 'The reset is now complete.',
            'We are now resetting Codex rate limits.', "We're resetting Codex limits.",
            'We have now fixed this issue and are reseting the rate limit for all users.',
            'Reset done. How are we doing?', "And it's done. See you tomorrow for some good news.",
        ]
        for text in examples:
            with self.subTest(text=text):
                result=p.CodexResetsProvider().parse(payload(dict(record(),text=text)))[0]
                self.assertEqual(result['kind'],'reset')
                self.assertEqual(result['implementation'],'reported_completed')

    def test_fetch_uses_fixed_endpoint_no_credentials_and_conditional_headers(self):
        calls=[]
        def opener(request,timeout):
            calls.append((request,timeout))
            return Response(json.dumps(payload(record())).encode(),headers={'ETag':'"new"'})
        result=p.CodexResetsProvider(opener).fetch(etag='"old"',timeout=100)
        request,timeout=calls[0]
        self.assertEqual(request.full_url,p.STATUS_URL)
        self.assertEqual(request.get_header('If-none-match'),'"old"')
        self.assertEqual(request.get_header('Cache-control'),'no-cache')
        self.assertFalse(request.has_header('Authorization'));self.assertFalse(request.has_header('Cookie'))
        self.assertIsNone(request.data);self.assertEqual(timeout,15)
        self.assertEqual(result.etag,'"new"')

    def test_http_304_and_retry_after(self):
        def unchanged(*a,**k):raise urllib.error.HTTPError(p.STATUS_URL,304,'Not modified',{'ETag':'"same"'},None)
        self.assertTrue(p.CodexResetsProvider(unchanged).fetch(etag='"same"').not_modified)
        def limited(*a,**k):raise urllib.error.HTTPError(p.STATUS_URL,429,'Limited',{'Retry-After':'3600'},None)
        with self.assertRaises(p.ProviderError) as exc:p.CodexResetsProvider(limited).fetch()
        self.assertEqual(exc.exception.retry_after,3600)
        self.assertEqual(p.retry_after(formatdate(NOW+120,usegmt=True),NOW),120)
        self.assertEqual(p.retry_after('172800',NOW),172800)
        for bad in ('nan','inf','-1','not a date'):self.assertIsNone(p.retry_after(bad,NOW))

    def test_response_limits_final_origin_and_redirect(self):
        for response in (Response(b'a'*(p.MAX_BYTES+1)),Response(b'{}',url='https://evil.test/data'),
                         Response(b'{}',headers={'Content-Length':'100'})):
            with self.assertRaises(p.ProviderError):p.CodexResetsProvider(lambda *a,**k:response).fetch()
        redirect=p._SameHostRedirect('codex-resets.com')
        request=p.urllib.request.Request(p.STATUS_URL)
        for url in ('http://codex-resets.com/data','https://evil.test/data','https://user@codex-resets.com/data'):
            with self.assertRaises(p.ProviderError):redirect.redirect_request(request,None,302,'',{},url)

    def test_invalid_etag_cannot_inject_headers(self):
        calls=[]
        def opener(request,timeout):calls.append(request);return Response(b'{}')
        p.fetch_bytes(p.STATUS_URL,host='codex-resets.com',etag='bad\r\nCookie: secret',opener=opener)
        self.assertFalse(calls[0].has_header('If-none-match'))

    def test_slow_stream_total_deadline_stops_before_other_source_is_starved(self):
        clock=[0.]
        class Trickle(Response):
            def read1(self,size):clock[0]+=4;return b'x'
        with patch.object(p.time,'monotonic',side_effect=lambda:clock[0]):
            with self.assertRaises(p.ProviderError) as exc:
                p.fetch_bytes(p.STATUS_URL,host='codex-resets.com',timeout=10,
                              opener=lambda *a,**k:Trickle(b''))
        self.assertEqual(exc.exception.code,'timeout')
        self.assertEqual(clock[0],12)

    def test_rss_latest_uses_date_plain_text_and_never_reset_kind(self):
        xml=b'''<rss version="2.0"><channel><item><title>Old</title><link>https://developers.openai.com/codex/changelog/#old</link><guid>old</guid><pubDate>Mon, 26 Oct 2026 00:00:00 GMT</pubDate></item><item><title>New reset limits</title><link>https://developers.openai.com/codex/changelog/#new</link><guid>new</guid><pubDate>Tue, 27 Oct 2026 00:00:00 GMT</pubDate><description>&lt;p&gt;Release &amp;amp; fixes&lt;/p&gt;&lt;script&gt;bad()&lt;/script&gt;&lt;style&gt;hidden&lt;/style&gt;</description></item></channel></rss>'''
        values=p.OfficialProductProvider().parse(xml)
        self.assertEqual(len(values),1);self.assertEqual(values[0]['id'],'new')
        self.assertEqual(values[0]['kind'],'update')
        self.assertIn('Release & fixes',values[0]['text']);self.assertNotIn('bad()',values[0]['text'])
        self.assertNotIn('hidden',values[0]['text'])

    def test_rss_rejects_dtd_entities_unknown_shapes_and_foreign_links(self):
        for raw in (b'<!DOCTYPE rss [<!ENTITY x SYSTEM "file:///etc/passwd">]><rss version="2.0"><channel/></rss>',
                    b'<feed/>',b'<rss version="2.0"><channel/></rss>',b'<rss version="2.0">\0</rss>'):
            with self.assertRaises(p.ProviderError):p.OfficialProductProvider().parse(raw)
        for url in ('https://evil.test/changelog','https://developers.openai.com/unrelated','javascript:alert(1)'):
            with self.assertRaises(ValueError):p.OfficialProductProvider.validate_link(url)

    def test_real_saved_fixtures_parse_without_network(self):
        fixtures=Path(__file__).resolve().parents[2]/'verification/public-sources'
        if not (fixtures/'codex-resets-v1-live.json').is_file():self.skipTest('saved public fixture not available')
        reset=p.CodexResetsProvider().parse(json.loads((fixtures/'codex-resets-v1-live.json').read_text()))
        self.assertEqual(reset[0]['id'],'2115330127886463244')
        self.assertEqual(reset[0]['kind'],'reset')
        rss=p.OfficialProductProvider().parse((fixtures/'codex-changelog-rss.xml').read_bytes())
        self.assertEqual(rss[0]['kind'],'update')
        self.assertTrue(rss[0]['text'].startswith('Codex CLI Release: 0.165.0'))


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='bailong-public-tests-');self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'public-announcements.json';self.a=FakeProvider();self.b=FakeProvider('codex_changelog')
        self.m=p.PublicAnnouncementMonitor(self.path,[self.a,self.b])

    def test_each_source_first_success_is_silent_even_after_other_source(self):
        self.b.error=p.ProviderError('network','offline')
        snapshot,alerts=self.m.poll(NOW)
        self.assertEqual(snapshot['state'],'degraded');self.assertEqual(alerts,[])
        self.b.error=None;self.b.result=p.FetchResult([item('20000',NOW+900)])
        snapshot,alerts=self.m.poll(NOW+900)
        self.assertEqual(snapshot['state'],'ok');self.assertEqual(alerts,[])

    def test_new_reset_once_official_update_never_sounds_and_restart_dedup(self):
        self.m.poll(NOW)
        self.a.result=p.FetchResult([item('10002',NOW+900)]*2,'"changed"')
        self.b.result=p.FetchResult([item('10003',NOW+900)])
        snapshot,alerts=self.m.poll(NOW+900)
        self.assertEqual([(a['id'],a['kind'],a['source_id']) for a in alerts],[('10002','reset','codex_resets')])
        self.assertTrue(self.path.is_file())
        reloaded=p.PublicAnnouncementMonitor(self.path,[self.a,self.b])
        self.assertEqual(reloaded.poll(NOW+1800)[1],[])
        self.assertEqual(self.a.calls[-1]['etag'],'"changed"')

    def test_etag_changing_same_event_is_silent(self):
        self.m.poll(NOW)
        self.a.result=p.FetchResult([item()],'"two"')
        self.assertEqual(self.m.poll(NOW+900)[1],[])
        self.assertEqual(self.m.states[self.a.id]['etag'],'"two"')

    def test_304_preserves_item_and_refreshes_success_but_invalid_304_fails(self):
        self.m.poll(NOW)
        self.a.result=p.FetchResult(etag='"one"',not_modified=True)
        snapshot,alerts=self.m.poll(NOW+900)
        source=snapshot['sources'][0]
        self.assertEqual(source['items'][0]['id'],'10001')
        self.assertEqual(source['last_success'],NOW+900);self.assertEqual(alerts,[])
        fresh=p.PublicAnnouncementMonitor(Path(self.temp.name)/'new.json',[self.a])
        source=fresh.poll(NOW)[0]['sources'][0]
        self.assertEqual(source['error_code'],'invalid_304');self.assertIsNone(source['last_success'])

    def test_source_backoff_retry_after_and_force_are_isolated(self):
        self.m.poll(NOW)
        self.a.error=p.ProviderError('http_429','limited',3600)
        self.b.result=p.FetchResult([item('b-new',NOW+900,kind='update')])
        snapshot,_=self.m.poll(NOW+900)
        self.assertEqual(snapshot['state'],'degraded')
        self.assertEqual(snapshot['sources'][0]['next_check'],NOW+4500)
        self.assertEqual(snapshot['sources'][1]['items'][0]['id'],'b-new')
        self.m.poll(NOW+901,force=True)
        self.assertEqual(len(self.a.calls),2)
        self.assertEqual(len(self.b.calls),3)
        self.assertEqual(self.m.states[self.a.id]['last_success'],NOW)

    def test_late_old_future_and_scheduled_deadline_are_silent(self):
        self.m.poll(NOW)
        self.a.result=p.FetchResult([item('late',NOW-86400)])
        self.assertEqual(self.m.poll(NOW+900)[1],[])
        self.a.result=p.FetchResult([item('scheduled',NOW+1800,kind='upcoming',scheduled_for=NOW+1900)])
        self.assertEqual(self.m.poll(NOW+1800)[1],[])
        self.assertEqual(self.m.poll(NOW+2700)[1],[])
        self.a.result=p.FetchResult([item('future',NOW+31536000)])
        self.assertEqual(self.m.poll(NOW+3600)[1],[])
        self.assertLess(self.m.states[self.a.id]['high_water'],NOW+31536000)
        self.a.result=p.FetchResult([item('real-new',NOW+4500)])
        self.assertEqual([a['id'] for a in self.m.poll(NOW+4500)[1]],['real-new'])

    def test_future_timestamp_cannot_ring_when_clock_catches_up(self):
        self.m.poll(NOW)
        self.a.result=p.FetchResult([item('future',NOW+3600)])
        self.m.poll(NOW+900)
        self.assertEqual(self.m.poll(NOW+3600)[1],[])

    def test_near_future_is_not_given_a_sound_clock_tolerance(self):
        self.m.poll(NOW)
        self.a.result=p.FetchResult([item('near-future',NOW+960)])
        snapshot,alerts=self.m.poll(NOW+900)
        self.assertEqual(alerts,[])
        self.assertEqual(snapshot['sources'][0]['items'][0]['kind'],'uncertain')
        self.assertEqual(self.m.poll(NOW+1800)[1],[])

    def test_future_reset_text_remains_silent_after_announced_time(self):
        self.m.poll(NOW)
        future=dict(record('10002',NOW+900),text='Team will reset rate limits in the next hour.')
        self.a.result=p.FetchResult(p.CodexResetsProvider().parse(payload(future)))
        snapshot,alerts=self.m.poll(NOW+900)
        self.assertEqual(alerts,[])
        self.assertEqual(snapshot['sources'][0]['items'][0]['kind'],'upcoming')
        self.assertEqual(self.m.poll(NOW+900+7200)[1],[])
        reloaded=p.PublicAnnouncementMonitor(self.path,[self.a,self.b])
        self.assertEqual(reloaded.poll(NOW+900+10800)[1],[])

    def test_negative_question_and_unknown_reports_cannot_generate_alerts(self):
        self.m.poll(NOW)
        examples=('We have not reset Codex limits yet.','Have Codex limits been reset?',
                  'A public update.','Suppose we reset Codex limits.')
        for index,text in enumerate(examples,1):
            published=NOW+index*900
            value=dict(record(str(10001+index),published),text=text)
            self.a.result=p.FetchResult(p.CodexResetsProvider().parse(payload(value)))
            snapshot,alerts=self.m.poll(published)
            self.assertEqual(alerts,[])
            self.assertEqual(snapshot['sources'][0]['items'][0]['kind'],'uncertain')

    def test_cache_write_failure_suppresses_alert_and_preserves_last_success(self):
        self.m.poll(NOW)
        self.a.result=p.FetchResult([item('10002',NOW+900)])
        with patch.object(p,'_atomic_json',side_effect=OSError('full')):
            snapshot,alerts=self.m.poll(NOW+900)
        self.assertEqual(alerts,[])
        self.assertEqual(snapshot['sources'][0]['last_success'],NOW)
        self.assertEqual(snapshot['sources'][0]['error_code'],'cache_write')

    def test_schema_failure_keeps_last_good_item_and_error_text_is_safe(self):
        self.m.poll(NOW)
        self.a.result=p.FetchResult([{'bad':'data'}])
        snapshot,alerts=self.m.poll(NOW+900)
        self.assertEqual(snapshot['sources'][0]['items'][0]['id'],'10001');self.assertEqual(alerts,[])
        self.a.error=OSError('secret request detail')
        snapshot,_=self.m.poll(NOW+1800)
        self.assertNotIn('secret',json.dumps(snapshot))

    def test_mute_disabled_reenable_and_unavailable_are_silent(self):
        self.m.poll(NOW);self.m.configure(sound_enabled=False)
        self.a.result=p.FetchResult([item('10002',NOW+900)])
        self.assertEqual(self.m.poll(NOW+900)[1],[])
        self.m.configure(sound_enabled=True)
        self.assertEqual(self.m.poll(NOW+1800)[1],[])
        self.m.configure(enabled=False);count=len(self.a.calls)
        self.assertEqual(self.m.poll(NOW+2700)[0]['state'],'disabled');self.assertEqual(len(self.a.calls),count)
        self.a.result=p.FetchResult([item('10003',NOW+3600)])
        self.m.configure(enabled=True);self.assertEqual(self.m.poll(NOW+3600)[1],[])
        self.a.available=False;self.m.poll(NOW+4500,force=True)
        self.assertEqual(len(self.a.calls),count+1)

    def test_latest_display_by_publication_and_cache_bounded(self):
        self.a.result=p.FetchResult([item('z-old',NOW-100),item('a-new',NOW-1,irrelevant_metadata='x'*1000000)])
        snapshot,_=self.m.poll(NOW)
        self.assertEqual(snapshot['sources'][0]['items'][0]['id'],'a-new')
        self.assertNotIn('irrelevant_metadata',snapshot['sources'][0]['items'][0])
        self.assertLess(self.path.stat().st_size,20000)


if __name__=='__main__':unittest.main()
