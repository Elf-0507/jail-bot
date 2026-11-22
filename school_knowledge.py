"""Local, source-linked retrieval from the official school website snapshot."""
from collections import Counter, defaultdict
from array import array
import gzip
import json
import math
from pathlib import Path
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

DATA_PATH = Path(__file__).parent / 'school_data' / 'knowledge.json.gz'


def terms(text):
    text = text.lower().replace('4무', '4無').replace('사무운동', '4無운동')
    words = re.findall(r'[가-힣無]+|[a-z]+|[0-9]+', text)
    result = []
    for word in words:
        if len(word) > 1:
            result.append(word)
            if re.search(r'[가-힣無]', word):
                result.extend(word[i:i+n] for n in (2, 3) for i in range(len(word)-n+1))
    return result


class SchoolKnowledge:
    def __init__(self, path=DATA_PATH):
        self.documents = []
        self.chunks = []
        # Compact integer pairs keep the archive index small on a Render instance.
        self.postings = defaultdict(lambda: array('I'))
        self.collected_at = ''
        self.error = None
        try:
            with gzip.open(path, 'rt', encoding='utf-8') as stream:
                payload = json.load(stream)
            self.documents = payload['documents']
            self.collected_at = payload['collected_at']
        except (OSError, ValueError, KeyError) as exc:
            self.error = type(exc).__name__
            return
        for doc in self.documents:
            text = doc['text']
            for start in range(0, max(1, len(text)), 1050):
                passage = text[start:start+1250]
                title_terms = Counter(terms(doc['title'] + ' ' + doc.get('category', '')))
                counts = Counter(terms(passage))
                counts.update({term: 4*count for term, count in title_terms.items()})
                idx = len(self.chunks)
                self.chunks.append({'doc': doc, 'text': passage, 'start': start, 'length': max(400, sum(counts.values()))})
                for term, count in counts.items():
                    self.postings[term].extend((idx, count))
        self.avg_length = sum(c['length'] for c in self.chunks) / max(1, len(self.chunks))

    def search(self, question, limit=5):
        original_question = question
        requested_category = next((name for name in ('공지사항', '가정통신문', '학교규칙', '학사게시판', '평가계획') if name in question), None)
        date_hint = None
        today = datetime.now(ZoneInfo('Asia/Seoul')).date()
        if '오늘' in question or '내일' in question or '모레' in question:
            date_hint = today + timedelta(days=2 if '모레' in question else 1 if '내일' in question else 0)
            question += f' {date_hint:%Y-%m-%d} {date_hint.month}월 {date_hint.day}일'
        month_hint = date_hint.strftime('%Y-%m') if date_hint else None
        if '이번 달' in question or '이번달' in question:
            month_hint = today.strftime('%Y-%m')
            question += f' {today.year}년 {today.month}월'
        month_match = re.search(r'(\d{1,2})월', question)
        if month_match and not month_hint:
            year_match = re.search(r'(20\d{2})년', question)
            month_hint = f'{int(year_match.group(1)) if year_match else today.year}-{int(month_match.group(1)):02}'
        day_match = re.search(r'(\d{1,2})월\s*(\d{1,2})일', question)
        if day_match and not date_hint:
            try:
                date_hint = today.replace(year=int(month_hint[:4]), month=int(day_match.group(1)), day=int(day_match.group(2)))
            except ValueError:
                pass
        if not month_hint and re.search(r'급식|식단|일정|행사', original_question):
            month_hint = today.strftime('%Y-%m')
        prefer_recent = bool(re.search(r'최신|최근', question))
        question = re.sub(r'알려\s*줘\S*|알려\s*주세요\S*|질문자쿤|제일콩|우리\s*학교|마산제일고등학교|마산제일고', ' ', question)
        question = re.sub(r'최신|최근', ' ', question)
        question = question.replace('야자', '야간자기주도적학습 야간자율학습')
        for word, expansion in {'휴대폰': '휴대전화', '핸드폰': '휴대전화', '교칙': '학교규칙',
                                '어디': '주소 찾아오시는 길', '전화': '연락처', '설립': '연혁'}.items():
            if word in question:
                question += ' ' + expansion
        question = re.sub(r'학교(?:가|는|의|에서)?|언제|뭐야|뭐가|있어', ' ', question)
        if '개교' in question or '설립' in question:
            question += ' 연혁'
        scores = defaultdict(float)
        size = len(self.chunks)
        for term in set(terms(question)):
            posting = self.postings.get(term, ())
            frequency = len(posting) // 2
            idf = math.log(1 + (size - frequency + .5) / (frequency + .5))
            for offset in range(0, len(posting), 2):
                idx, count = posting[offset], posting[offset+1]
                length = self.chunks[idx]['length']
                scores[idx] += idf * count * 2.2 / (count + 1.2*(.25+.75*length/max(1,self.avg_length)))
        query_words = set(re.findall(r'[가-힣無a-z]{2,}', question.lower())) - {'알려줘', '주세요', '종류', '뭐야', '오늘', '내일', '모레'}
        query_words = {re.sub(r'(?:에서|에게|이|가|은|는|의|을|를)$', '', word) for word in query_words}
        normalized_question = re.sub(r'\s+', '', question.lower())
        for idx in scores:
            chunk = self.chunks[idx]
            doc = chunk['doc']
            haystack = (doc['title'] + ' ' + chunk['text']).lower()
            covered = sum(word in haystack for word in query_words if word)
            scores[idx] *= .5 + 2 * covered / max(1, len(query_words))
            if '/cm/cntnts/' in doc['url']:
                scores[idx] *= 1.7
            if len(doc['title']) >= 2 and re.sub(r'\s+', '', doc['title'].lower()) in normalized_question:
                scores[idx] *= 2
        ranked = sorted(scores, key=lambda idx: (scores[idx], self.chunks[idx]['doc'].get('published_date', '')), reverse=True)
        if month_hint and re.search(r'급식|식단|일정|행사', original_question):
            ranked.sort(key=lambda idx: (self.chunks[idx]['doc'].get('calendar_month') == month_hint, scores[idx]), reverse=True)
        if prefer_recent:
            ranked.sort(key=lambda idx: (bool(month_hint) and self.chunks[idx]['doc'].get('calendar_month') == month_hint,
                                        re.sub(r'[./]', '-', self.chunks[idx]['doc'].get('published_date', '')), scores[idx]), reverse=True)
        selected, seen = [], set()
        for idx in ranked:
            chunk = self.chunks[idx]
            doc = chunk['doc']
            if requested_category and requested_category not in doc.get('category', '') and requested_category not in doc['title']:
                continue
            if month_hint and doc.get('calendar_month') and doc['calendar_month'] != month_hint:
                continue
            if doc['url'] in seen or scores[idx] < min(2, math.log1p(size) / 2):
                continue
            seen.add(doc['url'])
            passage = (doc['text'][:500] + '\n[…]\n' if chunk['start'] >= 500 else '') + chunk['text']
            if '/cm/cntnts/' in doc['url'] and len(doc['text']) <= 8000:
                passage = doc['text']
            if doc.get('calendar_month'):
                if date_hint:
                    date_label = date_hint.strftime('%Y/%m/%d')
                    blocks = []
                    for match in re.finditer(r'(?:^|\n)(\d{4}/\d{2}/\d{2})(?: ~ (\d{4}/\d{2}/\d{2}))?:.*?(?=\n\d{4}/\d{2}/\d{2}|\Z)', doc['text'], re.S):
                        if match.group(1) <= date_label <= (match.group(2) or match.group(1)):
                            blocks.append(match.group(0))
                    passage = doc['title'] + '\n' + ('\n'.join(blocks) if blocks else date_label + ': 이 스냅샷에는 해당 날짜 항목이 없음. 휴업·급식 미실시라고 단정할 수 없음.')
                else:
                    passage = doc['text'][:12000]
            selected.append({
                'number': len(selected)+1, 'title': doc['title'], 'url': doc['url'],
                'published_date': doc.get('published_date', ''),
                'text': passage,
                'has_unread_media': bool(doc.get('image_count') or doc.get('attachments')),
            })
            if len(selected) >= limit:
                break
        return selected

    def context(self, question):
        sources = self.search(question)
        context = json.dumps({'collected_at': self.collected_at, 'sources': sources}, ensure_ascii=False)
        return context, [{k: s[k] for k in ('number', 'title', 'url', 'published_date')} for s in sources]
