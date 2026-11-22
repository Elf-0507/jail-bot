"""Optional macOS OCR for image-based school introduction pages.

Requires a compiled ocr_school.swift utility. Does not download blocked attachments.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import time
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
import requests
from sync_school import AGENT, HOME, ROOT, canonical


def merge_ocr_data(snapshot, ocr_json):
    path = Path(snapshot)
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        payload = json.load(f)
    ocr = json.loads(Path(ocr_json).read_text())
    page_count = image_count = 0
    for doc in payload['documents']:
        records = ocr.get(doc['url'], [])
        texts = [r['text'] for r in records if len(r.get('text', '')) >= 5 and r.get('confidence', 0) >= .5]
        if texts:
            marker = '\n[이미지 문자 인식(OCR): 날짜·숫자·고유명사는 원문 재확인 필요]\n'
            base_text = doc['text'].split(marker)[0].replace('본문 텍스트 없음. 이미지 또는 첨부자료는 원문 확인 필요.', '').strip()
            doc['text'] = base_text + marker + '\n\n'.join(texts)
            doc['ocr_image_count'] = len(texts)
            page_count += 1
            image_count += len(texts)
    payload['coverage']['ocr'] = {'pages': page_count, 'images': image_count,
                                  'scope': '학교소개의 고정 콘텐츠 이미지',
                                  'limitations': 'OCR 오인식 가능. 게시판 사진 전체의 글자는 미추출.'}
    payload['coverage']['limitations'] = [line for line in payload['coverage'].get('limitations', []) if '이미지 속 글자' not in line]
    payload['coverage']['limitations'].append('학교소개 일부 이미지 OCR 보충. 게시판 사진 전체 및 동영상은 미추출.')
    with gzip.open(path, 'wt', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False)
    report_path = path.with_name('coverage.json')
    report = json.loads(report_path.read_text())
    report['coverage'] = payload['coverage']
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(payload['coverage']['ocr'], ensure_ascii=False))


def enrich(main_file, html_cache, image_cache, output, executable):
    main = BeautifulSoup(Path(main_file).read_text(), 'html.parser')
    urls = {canonical(a['href']) for a in main.select('a[href]')
            if canonical(a['href']) and 'cntntsView.do' in a['href']}
    cache = Path(image_cache)
    cache.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers['User-Agent'] = AGENT
    robots = RobotFileParser()
    r = session.get(ROOT + '/robots.txt', timeout=25)
    r.raise_for_status()
    robots.parse(r.text.splitlines())
    result = {}
    for url in sorted(urls):
        path = Path(html_cache) / (hashlib.sha256(url.encode()).hexdigest() + '.html')
        if not path.exists():
            continue
        soup = BeautifulSoup(path.read_text(), 'html.parser')
        records = []
        for image in soup.select('#cntntsView img[src]'):
            image_url = urljoin(url, image['src'])
            if urlsplit(image_url).hostname != urlsplit(ROOT).hostname or not robots.can_fetch(AGENT, image_url):
                continue
            target = cache / (hashlib.sha256(image_url.encode()).hexdigest() + '.image')
            record = {'url': image_url, 'alt': image.get('alt', '')}
            try:
                if not target.exists():
                    time.sleep(.5)
                    response = session.get(image_url, timeout=25)
                    response.raise_for_status()
                    if 'image/' not in response.headers.get('Content-Type', '') or len(response.content) > 10_000_000:
                        raise ValueError('not an image or too large')
                    target.write_bytes(response.content)
                ocr_file = target.with_suffix('.ocr.json')
                if ocr_file.exists():
                    recognized = json.loads(ocr_file.read_text())
                else:
                    recognized = json.loads(subprocess.check_output([executable, str(target)], timeout=90))[0]
                    ocr_file.write_text(json.dumps(recognized, ensure_ascii=False))
                record.update({key: recognized[key] for key in ('text', 'confidence', 'error') if key in recognized})
            except Exception as exc:
                record['error'] = type(exc).__name__
            records.append(record)
        if records:
            result[url] = records
            print(json.dumps({'page': url, 'images': len(records), 'characters': sum(len(x.get('text','')) for x in records)}, ensure_ascii=False), flush=True)
            Path(output).write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--main-file', required=True)
    p.add_argument('--html-cache', required=True)
    p.add_argument('--image-cache', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--executable', required=True)
    args = p.parse_args()
    enrich(args.main_file, args.html_cache, args.image_cache, args.output, args.executable)
