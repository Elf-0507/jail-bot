import gzip
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from school_knowledge import SchoolKnowledge
from sync_school import canonical, parse_page


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'data.json.gz'
        self.docs = [
            {'title': '청강학사 기숙사 안내', 'category': '기숙사', 'url': 'https://masanjeil-h.gne.go.kr/dorm',
             'text': '청강학사는 학교 기숙사입니다. 선발 기준은 매년 공지사항을 확인하세요.', 'published_date': ''},
            {'title': '학교 연혁', 'category': '학교소개', 'url': 'https://masanjeil-h.gne.go.kr/history',
             'text': '학교 설립과 개교에 관한 연혁 자료입니다.', 'published_date': ''},
        ]
        with gzip.open(self.path, 'wt') as f:
            json.dump({'collected_at': '2026-11-22T23:00:00+09:00', 'documents': self.docs}, f)
        self.knowledge = SchoolKnowledge(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_korean_search_and_sources(self):
        result = self.knowledge.search('기숙사 선발 기준 알려줘')
        self.assertEqual(result[0]['title'], '청강학사 기숙사 안내')
        context, sources = self.knowledge.context('기숙사 알려줘')
        self.assertIn('청강학사', context)
        self.assertEqual(sources[0]['number'], 1)
        self.assertNotIn('text', sources[0])

    def test_no_match_and_missing_data(self):
        self.assertEqual(self.knowledge.search('안녕'), [])
        missing = SchoolKnowledge(Path(self.temp.name) / 'missing.gz')
        self.assertEqual(missing.search('기숙사'), [])
        self.assertTrue(missing.error)

    def test_recent_notice_uses_publication_date(self):
        docs = [dict(self.docs[0], title='기숙사 공지사항', published_date='2025.03.01'),
                dict(self.docs[1], title='기숙사 공지사항', published_date='2026.11.20')]
        with gzip.open(self.path, 'wt') as f:
            json.dump({'collected_at': '2026-11-22', 'documents': docs}, f)
        self.assertEqual(SchoolKnowledge(self.path).search('최신 기숙사 공지사항')[0]['published_date'], '2026.11.20')

    def test_calendar_explicit_date_returns_only_that_day(self):
        doc = dict(self.docs[0], title='2026년 11월 점심식사 급식 식단', category='급식',
                   text='2026/11/20: 국수\n2026/11/23: 쌀밥\n된장국\n2026/11/24: 볶음밥', calendar_month='2026-11')
        with gzip.open(self.path, 'wt') as f:
            json.dump({'collected_at': '2026-11-22', 'documents': [doc]}, f)
        result = SchoolKnowledge(self.path).search('2026년 11월 23일 급식')
        self.assertIn('쌀밥', result[0]['text'])
        self.assertIn('된장국', result[0]['text'])
        self.assertNotIn('볶음밥', result[0]['text'])

    def test_only_read_only_school_pages(self):
        self.assertIsNone(canonical('https://example.com/file'))
        self.assertIsNone(canonical('/common/nttFileDownload.do?fileKey=x'))
        self.assertIsNone(canonical('/masanjeil-h/na/ntt/deleteNttInfo.do'))
        self.assertIn('currPage=2', canonical('/masanjeil-h/na/ntt/selectNttList.do?mi=1&currPage=2'))

    def test_extracts_body_and_records_unread_media(self):
        html = '''<div class="sub_content_wb">본문밖메뉴<input id="nttSj" value="기숙사 안내"><form id="nttViewForm"><div class="BD_table">
        <table><tr><th>작성자</th><td>테스트작성자</td><th>등록일</th><td>2026.11.20</td></tr>
        <tr><td>기숙사 안내 본문입니다.<img src="poster.png"></td></tr>
        <tr><th>첨부파일</th><td><a href="/common/nttFileDownload.do?fileKey=x">규정.hwp</a></td></tr></table>
        </div></form><nav>관계없는 메뉴</nav></div>'''
        doc, error = parse_page(html, 'https://masanjeil-h.gne.go.kr/masanjeil-h/na/ntt/selectNttInfo.do?nttSn=1', '기숙사')
        self.assertIsNone(error)
        self.assertIn('기숙사 안내 본문', doc['text'])
        self.assertNotIn('테스트작성자', doc['text'])
        self.assertNotIn('관계없는 메뉴', doc['text'])
        self.assertNotIn('본문밖메뉴', doc['text'])
        self.assertEqual(doc['published_date'], '2026.11.20')
        self.assertEqual(doc['attachments'], ['규정.hwp'])
        self.assertEqual(doc['image_count'], 1)

    def test_chat_passes_context_and_only_returns_cited_sources(self):
        import app as bot
        with patch.object(bot, 'school_knowledge', self.knowledge), patch.object(bot.model, 'generate_content') as generate:
            generate.return_value = SimpleNamespace(text='제일콩이 찾아봤어요오~ 청강학사는 학교 기숙사예요! [1]')
            response = bot.app.test_client().post('/chat', json={'message': '기숙사 알려줘'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('청강학사', generate.call_args.args[0])
        self.assertEqual(len(response.json['sources']), 1)
        self.assertIn('knowledge_updated_at', response.json)
        self.assertNotIn('피티짱', bot.jeil_setting)
        self.assertNotIn('포청관', bot.jeil_setting)

    def test_chat_invalid_input(self):
        import app as bot
        with patch.object(bot.model, 'generate_content') as generate:
            for data in [[], {}, {'message': None}, {'message': ' '}, {'message': '가'*8001}]:
                self.assertEqual(bot.app.test_client().post('/chat', json=data).status_code, 400)
            generate.assert_not_called()

    def test_school_image_question_is_not_image_generation(self):
        import app as bot
        with patch.object(bot, 'school_knowledge', self.knowledge), patch.object(bot.model, 'generate_content') as generate:
            generate.return_value = SimpleNamespace(text='학교상징 원문을 확인해 주세요오~!')
            response = bot.app.test_client().post('/chat', json={'message': '학교상징 그림의 의미가 뭐야?'})
        self.assertNotIn('image_url', response.json)
        self.assertIn('공식 홈페이지 참고자료', generate.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
