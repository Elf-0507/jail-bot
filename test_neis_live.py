from datetime import date
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import requests
from neis_live import NeisLive, dates_for

TODAY = date(2026, 11, 22)


def api_result(service, rows=None, code='INFO-000'):
    if code != 'INFO-000':
        return {'RESULT': {'CODE': code}}
    return {service: [{'head': [{'RESULT': {'CODE': code}}]}, {'row': rows or []}]}


class LiveTests(unittest.TestCase):
    def test_dates(self):
        self.assertEqual(dates_for('내일 급식', TODAY), (date(2026,11,23),)*2)
        self.assertEqual(dates_for('다음 주 시간표', TODAY), (date(2026,11,23),date(2026,11,27)))
        self.assertEqual(dates_for('2026-12-01 급식', TODAY), (date(2026,12,1),)*2)

    def test_pending_keeps_date_and_requests_class(self):
        client = NeisLive('test-secret')
        pending = client.answer('내일 시간표', today=TODAY)['pending_neis']
        with patch.object(client, 'fetch', return_value=([
            {'ALL_TI_YMD':'20261123', 'GRADE':'1', 'CLASS_NM':'2', 'PERIO':'1', 'ITRT_CNTNT':'공통국어2'}
        ], '2026-11-22T23:00:00+09:00')) as fetch:
            answer = client.answer('1학년 2반', pending, TODAY)
        self.assertIn('공통국어2', answer['reply'])
        self.assertEqual(fetch.call_args.args, ('hisTimetable',date(2026,11,23),date(2026,11,23),1,2))

    def test_lunch_is_filtered_and_html_is_cleaned(self):
        client = NeisLive('test-secret')
        with patch.object(client, 'fetch', return_value=([
            {'MLSV_YMD':'20261123','MMEAL_SC_CODE':'1','MMEAL_SC_NM':'조식','DDISH_NM':'죽'},
            {'MLSV_YMD':'20261123','MMEAL_SC_CODE':'2','MMEAL_SC_NM':'중식','DDISH_NM':'밥<br/>국 (5.6)','CAL_INFO':'800 Kcal'},
            {'MLSV_YMD':'20231123','MMEAL_SC_CODE':'2','DDISH_NM':'옛날식단'},
        ], '2026-11-22T23:00:00+09:00')):
            answer = client.answer('내일 점심', today=TODAY)
        self.assertIn('밥\n국 (5.6)',answer['reply'])
        self.assertNotIn('죽',answer['reply'])
        self.assertNotIn('옛날식단',answer['reply'])

    def test_missing_key_and_invalid_dates_do_not_call_api(self):
        client = NeisLive('')
        with patch('neis_live.requests.get') as get:
            self.assertIn('API 키', client.answer('내일 급식', today=TODAY)['reply'])
            self.assertIn('날짜', client.answer('2월 30일 급식', today=TODAY)['reply'])
            client.answer('내일 9학년 1반 시간표', today=TODAY)
            get.assert_not_called()

    def test_api_key_is_only_in_server_request_and_cache_works(self):
        service = 'mealServiceDietInfo'
        response = Mock()
        response.json.return_value = api_result(service, [{'MLSV_YMD':'20261123','MMEAL_SC_CODE':'2','MMEAL_SC_NM':'중식','DDISH_NM':'쌀밥'}])
        client = NeisLive('test-secret')
        with patch('neis_live.requests.get', return_value=response) as get:
            answer = client.answer('내일 급식', today=TODAY)
            client.answer('내일 급식', today=TODAY)
        self.assertEqual(get.call_count,1)
        self.assertEqual(get.call_args.kwargs['params']['KEY'],'test-secret')
        self.assertEqual(get.call_args.kwargs['params']['SD_SCHUL_CODE'],'9010092')
        self.assertNotIn('test-secret',str(answer))

    def test_no_data_is_distinct_from_error_and_does_not_fabricate(self):
        response = Mock()
        response.json.return_value = api_result('mealServiceDietInfo', code='INFO-200')
        with patch('neis_live.requests.get',return_value=response):
            answer=NeisLive('test-secret').answer('오늘 급식',today=TODAY)
        self.assertIn('등록 정보가 없',answer['reply'])
        self.assertIn('live_fetched_at',answer)
        with patch('neis_live.requests.get',side_effect=requests.Timeout('https://example/?KEY=test-secret')):
            answer=NeisLive('test-secret').answer('오늘 급식',today=TODAY)
        self.assertIn('연결하지 못',answer['reply'])
        self.assertNotIn('test-secret',str(answer))
        self.assertNotIn('live_fetched_at',answer)

    def test_chat_bypasses_model_for_live_requests(self):
        import app
        with patch.object(app.neis_live,'answer',return_value={'reply':'실시간 조회 결과'}) as live, patch.object(app.model,'generate_content') as model:
            response=app.app.test_client().post('/chat',json={'message':'오늘 급식'})
        self.assertEqual(response.json['reply'],'실시간 조회 결과')
        model.assert_not_called()

    def test_general_school_info_stays_in_knowledge_path(self):
        self.assertIsNone(NeisLive('').answer('급식실 위치가 어디야?',today=TODAY))
        self.assertIsNone(NeisLive('').answer('학교상징 알려줘',today=TODAY))


if __name__ == '__main__':
    unittest.main()
