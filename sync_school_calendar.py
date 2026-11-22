"""Snapshot the public calendar feeds used by the school's own pages."""
import argparse
import calendar
import gzip
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
import requests
from sync_school import ROOT, AGENT


def collect(year, output):
    session = requests.Session()
    session.headers['User-Agent'] = AGENT
    robot = RobotFileParser()
    r = session.get(ROOT + '/robots.txt', timeout=25)
    r.raise_for_status()
    robot.parse(r.text.splitlines())
    documents, errors, checked = [], [], []
    for y, month in [(year, m) for m in range(1, 13)] + [(year+1, 1), (year+1, 2)]:
        first = f'{y}/{month:02}/01'
        last = f'{y}/{month:02}/{calendar.monthrange(y,month)[1]}'
        tasks = [('학사일정', '/masanjeil-h/sv/schdulView/selectSvList.do', None)]
        tasks += [('급식', '/masanjeil-h/dv/dietView/selectDvList.do', kind) for kind in ('아침식사', '점심식사', '저녁식사')]
        for kind, endpoint, diet in tasks:
            body = {'sysId': 'masanjeil-h', 'monthFirst': first, 'monthEnmt': last}
            if diet:
                body['dietTy'] = diet
            if not robot.can_fetch(AGENT, ROOT + endpoint):
                errors.append({'endpoint': endpoint, 'month': first, 'reason': 'robots_disallowed'})
                continue
            try:
                time.sleep(.4)
                # This POST only reads the same public data as the website calendar.
                r = session.post(ROOT + endpoint, data=body, timeout=25)
                r.raise_for_status()
                rows = r.json()
                if not isinstance(rows, list):
                    raise ValueError('unexpected calendar response')
                lines = []
                for row in rows:
                    date = row.get('dietDate' if diet else 'bgnde', '').replace('-', '/')[:10]
                    if not date.startswith(f'{y}/{month:02}/'):
                        continue
                    value = row.get('dietCn' if diet else 'schdulTitle', '')
                    if not value:
                        continue
                    text = BeautifulSoup(value, 'html.parser').get_text(' ', strip=True)
                    end = '' if diet else row.get('endde', '')
                    lines.append(f'{date}' + (f' ~ {end}' if end and end != date else '') + ': ' + text)
                checked.append({'month': first[:7], 'kind': diet or kind, 'rows': len(lines)})
                if not lines:
                    continue
                page = '/masanjeil-h/dv/dietView/selectDietCalendarView.do' if diet else '/masanjeil-h/sv/schdulView/schdulCalendarView.do'
                query = {'mi': '157799' if diet else '506645', 'monthFirst': first, 'monthEnmt': last}
                if diet:
                    query['dietTy'] = diet
                url = ROOT + page + '?' + urlencode(query)
                title = f'{y}년 {month}월 ' + (diet + ' 급식 식단' if diet else '월간 학사일정')
                documents.append({'id': hashlib.sha256(url.encode()).hexdigest()[:16],
                                  'url': url, 'title': title, 'category': kind,
                                  'published_date': '', 'text': title + '\n' + '\n'.join(lines),
                                  'image_count': 0, 'attachments': [], 'calendar_month': f'{y}-{month:02}'})
            except Exception as exc:
                errors.append({'endpoint': endpoint, 'month': first, 'kind': diet or kind, 'reason': type(exc).__name__})
        print(json.dumps({'month': first[:7], 'documents': len(documents), 'errors': len(errors)}), flush=True)
    Path(output).write_text(json.dumps({'documents': documents, 'checked': checked, 'errors': errors}, ensure_ascii=False))


def merge(snapshot, calendar_json):
    path = Path(snapshot)
    with gzip.open(path, 'rt') as f:
        data = json.load(f)
    extra = json.loads(Path(calendar_json).read_text())
    ids = {d['id'] for d in extra['documents']}
    data['documents'] = [d for d in data['documents'] if d['id'] not in ids] + extra['documents']
    data['coverage']['calendar'] = {k: v for k, v in extra.items() if k != 'documents'}
    data['coverage']['calendar']['document_count'] = len(extra['documents'])
    data['coverage']['limitations'] = [line for line in data['coverage'].get('limitations', []) if '동적 달력' not in line]
    data['coverage']['limitations'].append('달력: 지정한 연도 1월부터 다음 해 2월까지 조회; 전체 과거·미래는 미수집')
    with gzip.open(path, 'wt') as f:
        json.dump(data, f, ensure_ascii=False)
    report_path = path.with_name('coverage.json')
    report = json.loads(report_path.read_text())
    report['coverage'] = data['coverage']
    report['document_count'] = len(data['documents'])
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--year', type=int, required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    collect(args.year, args.output)
