"""Collect public school HTML. Run explicitly; never crawls during a chat request."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import gzip
import hashlib
import json
from pathlib import Path
import re
import time
import threading
import tempfile
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
import requests

ROOT = 'https://masanjeil-h.gne.go.kr'
HOME = ROOT + '/masanjeil-h/main.do'
AGENT = 'JeilkongSchoolKnowledge/1.0'
READ_PATHS = {'main.do', 'cntntsView.do', 'selectSongSymbolInfo.do', 'view.do',
              'selectNttList.do', 'selectNttInfo.do', 'schdulCalendarView.do',
              'selectDietCalendarView.do', 'schlState.do', 'civCompInfo.do',
              'rcritPblanc.do', 'openInfoSys.do', 'openApi.do', 'infoApply.do',
              'openInfoCprEm.do'}


def clean(text):
    return '\n'.join(filter(None, (re.sub(r'\s+', ' ', line).strip() for line in text.splitlines())))


def canonical(href, base=HOME):
    p = urlsplit(urljoin(base, href))
    if p.hostname != urlsplit(ROOT).hostname or not p.path.startswith('/masanjeil-h/'):
        return None
    if p.path.rsplit('/', 1)[-1] not in READ_PATHS:
        return None
    params = dict(parse_qsl(p.query))
    allowed = ('mi', 'cntntsId', 'bbsId', 'nttSn', 'currPage')
    query = urlencode(sorted((k, v) for k, v in params.items() if k in allowed))
    return urlunsplit(('https', p.netloc, p.path, query, ''))


def parse_page(html, url, label=''):
    soup = BeautifulSoup(html, 'html.parser')
    region = (soup.select_one('#cntntsView') or soup.select_one('#nttViewForm .BD_table')
              or soup.select_one('.sub_content_wb'))
    if region is None:
        return None, 'no_public_body'
    # A login/error page must not become knowledge about the school.
    if not soup.select_one('#cntntsView, #nttViewForm') and re.search(
            r'로그인.*필요|접근.*권한|열람.*권한', region.get_text(' ', strip=True)):
        return None, 'access_restricted'
    title_node = soup.select_one('#nttSj')
    title = title_node.get('value') if title_node else label
    if not title:
        meta = soup.select_one('meta[name="keywords"]')
        title = meta.get('content', '').split(',')[-1] if meta else '학교 공식 자료'
    attachment_names = [clean(a.get_text(' ', strip=True)) for a in region.select('a[href*="nttFileDownload"]')]
    image_count = len(region.select('img'))
    dates = []
    for heading in region.find_all('th'):
        if heading.get_text(strip=True) in ('작성일', '등록일'):
            cell = heading.find_next_sibling('td')
            if cell:
                dates = re.findall(r'20\d{2}[.\-/]\d{2}[.\-/]\d{2}', cell.get_text())
                break
    for tag in region.select('script, style, form form, button, input, select, textarea, .btn_st, .common_display_none, [hidden]'):
        tag.decompose()
    # Do not index authors, counters, or download widgets as factual content.
    for tr in region.select('tr'):
        headings = ' '.join(t.get_text(' ', strip=True) for t in tr.find_all('th'))
        if '작성자' in headings or '첨부파일' in headings:
            tr.decompose()
    for element in region.select('.bbs_prev, .bbs_next, .bbsV_pager, .prev_next'):
        element.decompose()
    text = clean(region.get_text('\n', strip=True))
    if len(text) < 10 and not image_count and not attachment_names:
        return None, 'empty_body'
    doc = {'id': hashlib.sha256(url.encode()).hexdigest()[:16], 'url': url,
           'title': clean(title or label), 'category': label,
           'published_date': dates[0] if dates and 'selectNttInfo.do' in url else '',
           'text': text, 'image_count': image_count, 'attachments': attachment_names}
    if not text:
        doc['text'] = '본문 텍스트 없음. 이미지 또는 첨부자료는 원문 확인 필요.'
    return doc, None


def crawl(output, max_pages=10000, workers=3, cache_dir=None):
    # A normal refresh must fetch fresh data. Explicit --cache-dir resumes a run.
    cache = Path(cache_dir or tempfile.mkdtemp(prefix='jeilkong-school-'))
    cache.mkdir(parents=True, exist_ok=True)
    robots = RobotFileParser()
    response = requests.get(ROOT + '/robots.txt', timeout=25, headers={'User-Agent': AGENT})
    response.raise_for_status()
    robots.parse(response.text.splitlines())
    skipped, docs, visited = [], {}, set()
    sessions = threading.local()

    def fetch(item):
        url, label = item
        if not robots.can_fetch(AGENT, url):
            return item, None, 'robots_disallowed'
        path = cache / (hashlib.sha256(url.encode()).hexdigest() + '.html')
        if path.exists():
            return item, path.read_text(), None
        for attempt in range(2):
            try:
                time.sleep(.4)
                if not hasattr(sessions, 'client'):
                    sessions.client = requests.Session()
                    sessions.client.max_redirects = 6
                    sessions.client.headers['User-Agent'] = AGENT
                r = sessions.client.get(url, timeout=25)
                r.raise_for_status()
                if (urlsplit(r.url).hostname != urlsplit(ROOT).hostname or r.status_code != 200
                        or 'text/html' not in r.headers.get('Content-Type', '')):
                    return item, None, 'redirect_or_non_html'
                r.encoding = 'utf-8'
                path.write_text(r.text)
                return item, r.text, None
            except requests.RequestException as e:
                if attempt:
                    return item, None, type(e).__name__

    _, main, error = fetch((HOME, '홈페이지'))
    if error:
        raise RuntimeError(error)
    menu = {}
    for a in BeautifulSoup(main, 'html.parser').select('a[href]'):
        url = canonical(a['href'])
        if url and url != HOME:
            menu[url] = clean(a.get_text(' ', strip=True))
    queue = list(menu.items())
    footer = BeautifulSoup(main, 'html.parser').select_one('footer')
    if footer:
        docs[HOME] = {'id': 'school_contact', 'url': HOME, 'title': '학교 주소 및 연락처',
                      'category': '학교 연락처', 'published_date': '',
                      'text': clean(footer.get_text('\n', strip=True)), 'image_count': 0, 'attachments': []}
    boards = {}
    reached_limit = False
    with ThreadPoolExecutor(max_workers=workers) as pool:
        while queue:
            batch = []
            while queue and len(batch) < 40:
                item = queue.pop(0)
                if item[0] not in visited:
                    if len(visited) >= max_pages:
                        reached_limit = True
                        break
                    visited.add(item[0])
                    batch.append(item)
            if not batch:
                break
            for (url, label), html, error in pool.map(fetch, batch):
                if error:
                    skipped.append({'url': url, 'reason': error})
                    continue
                soup = BeautifulSoup(html, 'html.parser')
                if 'selectNttList.do' in url:
                    region = soup.select_one('.sub_content_wb')
                    if not region:
                        skipped.append({'url': url, 'reason': 'no_public_list'})
                        continue
                    links = []
                    for a in region.select('a[href*="selectNttInfo.do"]'):
                        target = canonical(a['href'], url)
                        if target:
                            links.append((target, label))
                    queue.extend(links)
                    q = dict(parse_qsl(urlsplit(url).query))
                    if 'currPage' not in q:
                        total = soup.select_one('.board-total')
                        match = re.search(r'/\s*([\d,]+)\s*페이지', total.get_text(' ', strip=True)) if total else None
                        pages = int(match.group(1).replace(',', '')) if match else 1
                        boards[label] = {'url': url, 'pages': pages}
                        for page in range(2, pages + 1):
                            queue.append((canonical(url + '&currPage=' + str(page)), label))
                    if not links:
                        skipped.append({'url': url, 'reason': 'empty_or_restricted_list'})
                    continue
                doc, reason = parse_page(html, url, label)
                if doc:
                    docs[url] = doc
                    region = soup.select_one('#cntntsView, #nttViewForm .BD_table, .sub_content_wb')
                    for anchor in region.select('a[href]') if region else []:
                        target = canonical(anchor['href'], url)
                        if target and target not in visited:
                            queue.append((target, label))
                else:
                    skipped.append({'url': url, 'reason': reason})
            print(json.dumps({'visited': len(visited), 'documents': len(docs), 'queued': len(queue), 'skipped': len(skipped)}, ensure_ascii=False), flush=True)
    payload = {'schema_version': 1, 'source': HOME,
               'collected_at': datetime.now().astimezone().isoformat(),
               'coverage': {'menus': menu, 'boards': boards, 'visited_pages': len(visited),
                            'limit_reached': reached_limit, 'remaining_queue': len(queue),
                            'skipped': skipped,
                            'limitations': ['로그인/권한 제한 자료 제외', '첨부파일 다운로드는 robots.txt에 따라 제외',
                                            '이미지 속 글자와 동영상 내용은 미추출', '동적 달력의 과거/미래 월 전체는 미수집',
                                            '외부 사이트 링크는 수집 범위 밖']},
               'documents': list(docs.values())}
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(target, 'wt', encoding='utf-8') as stream:
        json.dump(payload, stream, ensure_ascii=False)
    report = {k: v for k, v in payload.items() if k != 'documents'}
    report['document_count'] = len(docs)
    report['image_pages'] = sum(bool(d['image_count']) for d in docs.values())
    report['attachment_pages'] = sum(bool(d['attachments']) for d in docs.values())
    target.with_name('coverage.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print('SAVED', target, len(docs), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default=str(Path(__file__).parent / 'school_data' / 'knowledge.json.gz'))
    parser.add_argument('--max-pages', type=int, default=10000)
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--cache-dir')
    args = parser.parse_args()
    crawl(args.output, args.max_pages, args.workers, args.cache_dir)
