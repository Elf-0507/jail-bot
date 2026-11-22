# 제일봇 · 제일콩

마산제일고 마스코트 제일콩의 말투로 대답하는 Flask/Gemini 챗봇입니다.

## 공식 홈페이지 자료 연결

- `school_data/knowledge.json.gz`: 학교 공식 홈페이지 공개 본문 스냅샷
- `school_data/coverage.json`: 수집 시각, 메뉴·게시판별 범위, 누락·오류 기록
- `sync_school_calendar.py`: 공개 학사일정·급식 달력 보충
- `school_knowledge.py`: 한국어 부분어 검색으로 질문과 관련 있는 문단을 선택
- `app.py`: 선택한 자료를 Gemini에 전달하고 인용한 원문의 링크를 반환
- `index.html`: 답변 아래 출처 및 자료 수집일 표시

이는 모델 재훈련이나 홈페이지 전체를 모델에 영구 암기시키는 작업이 아닙니다.
저장된 공식 자료를 질문마다 찾아 전달하는 방식입니다. 실시간 홈페이지 조회와 자동 갱신은 하지 않습니다.
기존 코드에 들어 있던 출처 미확인 학교생활 설명은 공식 자료 검색으로 대체했습니다.
제일콩의 말투와 기존 Gemini 연결은 유지합니다.

### 수집 범위와 한계

홈페이지 메뉴에 연결된 학교소개·기숙사·교육과정·규칙·소식 등 공개 HTML과 게시판 이전 페이지를 수집합니다.
학교소개 고정 페이지의 이미지 일부는 macOS Vision의 한국어 OCR로 보충합니다.
학교 홈페이지 robots.txt에서 금지한 첨부파일 다운로드, 로그인/권한 제한 자료, 외부 사이트는 수집하지 않습니다.
게시판 사진 전체, 동영상, 달력의 과거·미래 모든 월은 포함하지 않습니다. 현재 스냅샷의 달력 범위는 2026년 1월~2027년 2월입니다.
OCR의 날짜·숫자·고유명사는 오인식할 수 있으므로 중요한 내용은 원문 재확인이 필요합니다.
수집 실패·빈 게시판도 coverage.json에 기록합니다. 모든 정보를 빠짐없이 수집했다는 의미는 아닙니다.

지난 연도의 공지와 현재 규정을 구분하도록 작성일·수집일을 모델에 제공합니다.
수집된 자료에 근거가 없는 학교 정보는 모른다고 답하도록 지침을 설정합니다.
사용자가 묻지 않은 개인정보를 따로 수집하거나 로그인하지 않습니다.

## Render

- 기존 `GOOGLE_API_KEY` 환경 변수를 사용합니다.
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn app:app`
- 새 코드를 배포하면 포함된 스냅샷을 읽습니다. 서버 시작/질문 처리 중 전체 홈페이지를 수집하지 않습니다.
- API 제공자나 키를 변경할 필요가 없습니다.

## 자료 갱신

Python 환경에서:

```sh
pip install -r requirements.txt
python sync_school.py
python sync_school_calendar.py --year 2026 --output /tmp/calendar.json
python -c 'from sync_school_calendar import merge; merge("school_data/knowledge.json.gz", "/tmp/calendar.json")'
```

기본 제한은 10,000페이지이며 도달 여부를 coverage.json에 기록합니다.
실패한 수집을 재개할 때는 `--cache-dir PATH`로 기존 HTML 캐시를 지정할 수 있습니다.
일반 실행은 매번 새 캐시를 만들어 최신 자료를 가져옵니다.
갱신 결과를 검토한 뒤 스냅샷과 coverage.json을 커밋하고 재배포합니다.

고정 소개 페이지 이미지의 OCR 보충은 macOS에서 선택적으로 실행합니다:

```sh
swiftc ocr_school.swift -o /tmp/jeil-school-ocr
python enrich_school_images.py --main-file MAIN_HTML --html-cache HTML_CACHE --image-cache IMAGE_CACHE --output OCR_JSON --executable /tmp/jeil-school-ocr
python -c 'from enrich_school_images import merge_ocr_data; merge_ocr_data("school_data/knowledge.json.gz", "OCR_JSON")'
```

이미지 인식은 Render 실행에 필요하지 않으며 API 비용을 발생시키지 않습니다.
학교 홈페이지: https://masanjeil-h.gne.go.kr/masanjeil-h/main.do

## 확인

```sh
python -m unittest discover -p test_school_knowledge.py
```

검색·출처·입력 검증·HTML 추출 및 자료 파일 누락 처리를 확인합니다.
Gemini의 실제 응답은 별도로 실제 API 키가 있는 배포 환경에서 확인해야 합니다.
