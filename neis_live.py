"""Direct, server-side NEIS lookups. Never sends the API key to a browser or model."""
from datetime import date, datetime, timedelta
import html
import os
import re
import threading
import time
from zoneinfo import ZoneInfo

import requests

SOURCE = {'number': 1, 'title': '나이스 교육정보 개방 포털',
          'url': 'https://open.neis.go.kr/portal/mainPage.do', 'published_date': ''}


class NeisError(Exception):
    pass


def text(value):
    return html.unescape(re.sub(r'<[^>]*>', '', re.sub(r'<br\s*/?>', '\n', str(value), flags=re.I))).strip()


def dates_for(message, today):
    match = re.search(r'(20\d{2})[-./년]\s*(\d{1,2})[-./월]\s*(\d{1,2})일?', message)
    if match:
        target = date(*map(int, match.groups()))
    else:
        match = re.search(r'(\d{1,2})월\s*(\d{1,2})일|(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)', message)
        if match:
            month, day = match.groups()[:2] if match.group(1) else match.groups()[2:]
            target = date(today.year, int(month), int(day))
        else:
            target = today + timedelta(days=2 if '모레' in message else 1 if '내일' in message else -1 if '어제' in message else 0)
    if re.search(r'(?:이번|다음)\s*주|주간|일주일', message):
        base = target if match else today
        monday = base - timedelta(days=base.weekday())
        if re.search(r'다음\s*주', message):
            monday += timedelta(days=7)
        day = next((i for i, name in enumerate('월화수목금토일') if name+'요일' in message), None)
        if day is not None:
            return monday+timedelta(days=day), monday+timedelta(days=day)
        return monday, monday+timedelta(days=4)
    weekday = next((i for i, name in enumerate('월화수목금토일') if name+'요일' in message), None)
    if weekday is not None and not match:
        target = today + timedelta(days=(weekday-today.weekday()) % 7)
    return target, target


class NeisLive:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.cache = {}
        self.lock = threading.Lock()

    def fetch(self, service, start, end, grade=None, classroom=None):
        key = self.api_key if self.api_key is not None else (os.getenv('NEIS_API_KEY') or os.getenv('NEIS_KEY', ''))
        if not key.strip():
            raise NeisError('빼꼼…! 제일콩의 나이스 연결은 아직 준비 중이에요오. 서버에 API 키를 착 설정하면 급식이랑 시간표를 불러올 수 있답니다아 🎀')
        cache_key = (service, start, end, grade, classroom)
        with self.lock:
            cached = self.cache.get(cache_key)
            if cached and time.monotonic()-cached[0] < 300:
                return cached[1], cached[2]
        params = {'KEY': key.strip(), 'Type': 'json', 'pIndex': 1, 'pSize': 1000,
                  'ATPT_OFCDC_SC_CODE': 'S10', 'SD_SCHUL_CODE': '9010092'}
        fmt = lambda day: day.strftime('%Y%m%d')
        if service == 'mealServiceDietInfo':
            params.update(MLSV_FROM_YMD=fmt(start), MLSV_TO_YMD=fmt(end))
        else:
            params.update(TI_FROM_YMD=fmt(start), TI_TO_YMD=fmt(end), GRADE=grade, CLASS_NM=classroom)
        try:
            response = requests.get('https://open.neis.go.kr/hub/'+service, params=params, timeout=12)
            response.raise_for_status()
            body = response.json()
            blocks = body.get(service, [])
            result = body.get('RESULT')
            for block in blocks:
                for item in block.get('head', []):
                    if 'RESULT' in item:
                        result = item['RESULT']
            code = result.get('CODE') if isinstance(result, dict) else None
            if code == 'INFO-200':
                rows = []
            elif code != 'INFO-000':
                raise NeisError('어, 어라라?! 나이스 조회가 삐끗했어요오…! API 설정이나 서비스 상태를 콕 확인해 주세요 🎀')
            else:
                rows = [row for block in blocks for row in block.get('row', [])]
        except (requests.RequestException, ValueError, TypeError, AttributeError):
            # Exception text can contain the request URL and secret. Never expose/log it.
            raise NeisError('에에엣, 나이스에 연결하지 못했어요오…! 쪼끔 뒤에 다시 톡 요청해 주세요. 제일콩도 요기서 기다릴게요 🎀') from None
        fetched = datetime.now(ZoneInfo('Asia/Seoul')).isoformat()
        with self.lock:
            if len(self.cache) >= 128:
                self.cache.pop(next(iter(self.cache)))
            self.cache[cache_key] = (time.monotonic(), rows, fetched)
        return rows, fetched

    def answer(self, message, pending=None, today=None):
        today = today or datetime.now(ZoneInfo('Asia/Seoul')).date()
        is_time = '시간표' in message or '몇 교시' in message
        is_meal = bool(re.search(r'급식|식단|조식|중식|석식|(?:아침|점심|저녁)\s*(?:뭐|메뉴|밥|먹을|식사|알려)|^(?:오늘|내일|모레)?\s*(?:아침|점심|저녁)[?!.~\s]*$', message)) and not re.search(r'급식실|급식소|급식비|영양상담', message)
        continuation = isinstance(pending, dict) and pending.get('kind') == 'timetable' and bool(re.fullmatch(r'\s*\d\s*학년\s*\d{1,2}\s*반\s*(?:이야|이에요|이요|이예요|야|예요|요)?[.!~\s]*', message))
        if not (is_time or is_meal or continuation):
            return None
        try:
            if continuation:
                start, end = date.fromisoformat(pending['start']), date.fromisoformat(pending['end'])
                is_time = True
            else:
                start, end = dates_for(message, today)
            if not 2000 <= start.year <= 2099 or end < start or (end-start).days > 30:
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            return {'reply': '어, 어라라?! 날짜가 쪼끔 헷갈려요오…! 날짜를 콕 짚어서 다시 보내주세요 🎀 예: 11월 23일 급식, 내일 1학년 1반 시간표'}
        grade = re.search(r'(\d+)\s*학년', message)
        classroom = re.search(r'(\d+)\s*반', message)
        if is_time:
            if not grade or not classroom:
                return {'reply': '빼꼼…! 몇 학년 몇 반 시간표를 펼쳐드릴까요오? 학년이랑 반을 요기에 톡 알려주시면, 제일콩이 쏙 찾아드릴게요 🎀 예: 1학년 1반',
                        'pending_neis': {'kind': 'timetable', 'start': start.isoformat(), 'end': end.isoformat()}}
            grade, classroom = int(grade.group(1)), int(classroom.group(1))
            if grade not in (1, 2, 3) or not 1 <= classroom <= 30:
                return {'reply': '앗, 학년·반이 쪼끔 헷갈려요오…! 1~3학년 중에서 학년이랑 반을 다시 콕 알려주세요 🎀'}
        try:
            rows, fetched = self.fetch('hisTimetable' if is_time else 'mealServiceDietInfo', start, end, grade if is_time else None, classroom if is_time else None)
        except NeisError as exc:
            return {'reply': str(exc)}
        date_field = 'ALL_TI_YMD' if is_time else 'MLSV_YMD'
        rows = [r for r in rows if start.strftime('%Y%m%d') <= r.get(date_field, '') <= end.strftime('%Y%m%d')]
        label = start.isoformat() + (' ~ '+end.isoformat() if end != start else '')
        if is_time:
            rows = [r for r in rows if r.get('GRADE') == str(grade) and r.get('CLASS_NM') == str(classroom)]
            rows.sort(key=lambda r: (r.get('ALL_TI_YMD', ''), int(r.get('PERIO', 0))))
            lines = [f"{r.get('ALL_TI_YMD', '')} · {r.get('PERIO', '')}교시: {text(r.get('ITRT_CNTNT', ''))}" for r in rows]
            intro = f'짜잔~! 제일콩이 {label} {grade}학년 {classroom}반 시간표를 쏙 가져왔어요오!! 요기서 교시별로 하나씩 확인해 보세요 🎀'
        else:
            meal = '1' if re.search(r'조식|아침', message) else '3' if re.search(r'석식|저녁', message) else '2' if re.search(r'중식|점심', message) else None
            rows = [r for r in rows if not meal or r.get('MMEAL_SC_CODE') == meal]
            rows.sort(key=lambda r: (r.get('MLSV_YMD', ''), r.get('MMEAL_SC_CODE', '')))
            lines = [f"{r.get('MLSV_YMD', '')} · {text(r.get('MMEAL_SC_NM', '급식'))}\n{text(r.get('DDISH_NM', ''))}" + (f"\n{text(r['CAL_INFO'])}" if r.get('CAL_INFO') else '') for r in rows]
            intro = f'꼬르륵… 앗! 제일콩이 {label} 급식을 쏙 가져왔어요오!! 맛있는 소식, 요기에 펼쳐드릴게요 🎀'
        reply = intro + '\n\n' + '\n\n'.join(lines) if lines else f'어, 어라라…?! {label}에 해당하는 나이스 등록 정보가 없어요오. 그, 그런데요!! 이걸로 휴강이나 급식 미실시라고 단정하면 안 된답니다아. 학교 공지도 콕 확인해 주세요 🎀'
        return {'reply': reply + '\n\n요거는 나이스에 등록된 정보랍니다아! 학교 사정에 따라 바뀔 수 있으니, 변경 공지도 콕 확인해 주세요오~ [1]',
                'sources': [SOURCE], 'live_fetched_at': fetched}
