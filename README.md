# PyNotepad — Windows 메모장 재현판

`C:\Windows\System32\notepad.exe`(10.0.26100)를 REA + Ghidra로 분석해 Python/Tk로 다시 만든 메모장이다.
분석 근거와 원본과의 차이는 [docs/ANALYSIS.md](docs/ANALYSIS.md)에 정리했다.

## 실행

```powershell
# 콘솔 없이 실행
pythonw notepad.pyw
# 파일 열기
pythonw notepad.pyw C:\path\to\file.txt
# 또는 모듈로
python -m pynotepad [파일]
```

추가 패키지는 필요 없다 (Python 3.10+ 표준 라이브러리만 사용).

## 웹 버전

`web/` 폴더는 같은 메뉴·단축키·대화 상자·테마를 HTML/CSS/JavaScript로 다시 만든 브라우저용 메모장이다.
빌드 단계나 외부 라이브러리 없이 그대로 배포한다. 인코딩·찾기·마크다운 로직은 Python 모듈을 그대로 옮겼다.

- **배포**: `main` 브랜치에 push하면 GitHub Actions(`.github/workflows/pages.yml`)가 테스트 후 `web/`을 GitHub Pages에 올린다.
  처음 한 번은 저장소 **Settings > Pages > Build and deployment > Source**를 **GitHub Actions**로 바꿔야 한다.
  주소: `https://<사용자 이름>.github.io/<저장소 이름>/`
- **로컬에서 보기**: ES 모듈을 쓰므로 `index.html`을 더블클릭하면 동작하지 않는다. 서버를 띄워서 연다.
  ```powershell
  python -m http.server 8000 -d web   # 그다음 http://localhost:8000
  ```
- **테스트**: `node --test web/tests/logic.test.mjs` (Node 22 이상)
- **설정 저장**: 브라우저 `localStorage`(`pynotepad.settings`, 데스크톱과 같은 키 이름)

데스크톱 버전과 다른 점 (브라우저 제약):

| 기능 | 웹 버전 |
|---|---|
| 열기/저장 | Chrome·Edge: 파일 선택 창으로 열고 같은 파일에 바로 저장. Firefox·Safari: 저장할 때마다 다운로드 |
| 새로 만들기·새 창 단축키 | 없음 (Ctrl+N, Ctrl+Shift+N은 브라우저가 가로챔). 메뉴로는 사용 가능 |
| 끝내기 | 메뉴에서 뺌 (페이지가 탭을 닫을 수 없음). 저장 안 한 내용이 있으면 탭을 닫을 때 브라우저가 묻는다 |
| 붙여넣기 메뉴 | 브라우저가 클립보드 읽기를 허락해야 동작. Ctrl+V는 항상 동작 |
| 글꼴 | 글꼴 이름 입력(목록 제공) + 크기. 굵게·기울임은 없음. D2Coding은 CDN에서 불러옴 |
| 인쇄 | 브라우저 인쇄 창으로 본문만 인쇄 |
| 인코딩 판별 | BOM 없는 UTF-16은 `IsTextUnicode` 대신 간단한 규칙으로 판별 |
| 제목 표시줄 | 탭 제목이 `*이름 - 메모장`. 테마 색은 휴대폰 브라우저 주소 표시줄에만 적용 |
| 마크다운 미리 보기 | 표를 HTML 표로 그림 (데스크톱은 상자 문자) |

## 재현한 기능

- **파일**: 새로 만들기, 새 창, 열기, 저장, 다른 이름으로 저장(인코딩 선택), 인쇄, 끝내기, 저장 안 한 변경 확인
- **편집**: 실행 취소, 잘라내기/복사/붙여넣기/삭제, Google로 검색, 찾기/다음 찾기/이전 찾기, 바꾸기/모두 바꾸기, 줄 이동, 모두 선택, 시간/날짜(F5)
- **서식**: 자동 줄 바꿈, 글꼴(Windows 글꼴 대화 상자)
- **보기**: 확대/축소(10%~500%, 10% 단위, Ctrl+휠), 상태 표시줄(줄·열 / 배율 / 줄 끝 / 인코딩)
- **추가 기능 — 줄 번호**: 보기 > 줄 번호(L)로 켜고 끈다(기본 켬, 설정에 저장). 현재 줄 번호는 진하게 표시되고, 자동 줄 바꿈된 줄에는 첫 줄에만 번호가 붙는다. (`pynotepad/linenumbers.py`)
- **한글 조합 인라인 표시**: 조합 중인 글자(예: '고')를 IME의 작은 기본 글꼴 창 대신 커서 위치에 본문 글꼴·크기로 바로 그린다. Tk 8.6은 이 기능이 없어 Win32 창 프로시저를 서브클래싱해 구현했다. (`pynotepad/ime.py`)
- **마크다운 미리 보기**: `.md` 파일은 렌더링된 모습으로 열린다. 메뉴 막대 오른쪽의 `✎ 원본 보기` / `▶ 미리 보기` 버튼, 보기 > 마크다운 미리 보기, Ctrl+Shift+M으로 전환한다. 저장하지 않은 수정 내용도 바로 반영되며, 편집 명령(붙여넣기·바꾸기 등)을 쓰면 원본 보기로 자동 전환된다. 지원: 제목, 굵게/기울임/취소선, 코드, 코드 블록, 인용, 목록/할 일 목록, 표(정렬 포함), 링크(http/https/mailto만 열림), 구분선. (`pynotepad/markdown_view.py`, 외부 패키지 없음)
- **테마 — 종이 / 슬레이트**: 메뉴 막대 오른쪽 끝의 `테마: 종이 ▾` 드롭다운으로 바꾼다(기본: 종이, 설정에 저장). 테마마다 색, UI 글꼴, 창 아이콘, 문서 이름 줄(종이: `이름 [수정됨]`, 슬레이트: 문서 탭)이 달라지고, Windows 11에서는 제목 표시줄 색도 바뀐다. 설계는 [design/DESIGN.md](design/DESIGN.md). (`pynotepad/themes.py`)
- 도움말 메뉴는 의도적으로 제거했다.
- 글꼴: UI는 테마 글꼴(종이: IBM Plex Sans KR, 슬레이트: Noto Sans KR — `pynotepad/fonts/`에 함께 들어 있고 이 앱에서만 등록됨, 없으면 맑은 고딕), 본문 기본은 D2Coding 12pt(한글 고정폭, 없으면 Tk가 대체 글꼴 사용). Windows 기본 메뉴 막대는 글꼴 지정을 무시하므로 메뉴 막대를 Tk Menubutton으로 직접 그린다. 제목 표시줄 글꼴은 Windows가 정하므로 바꿀 수 없다.
- 원본과 같은 단축키, F1 제외 (Ctrl+W 끝내기, Ctrl+Insert 복사, Alt+Backspace 실행 취소, 숫자 패드 +/-/0 포함)
- 인코딩 자동 판별(BOM → `IsTextUnicode` → UTF-8 검사 → ANSI)과 저장 시 인코딩·줄 끝 유지
- `.LOG`로 시작하는 파일을 열면 끝에 시간/날짜 자동 기록
- NUL 문자 → 공백 치환, 1 GiB 이상 파일 거부, 최근 문서 등록
- 설정 저장: `%APPDATA%\PyNotepad\settings.json` (원본 레지스트리와 같은 키 이름)

## 구조

```
pynotepad/
  app.py         메인 창, 메뉴, 단축키, 모든 명령(cmd_*)
  dialogs.py     찾기/바꾸기, 줄 이동, 저장 확인, 인코딩 선택 대화 상자
  encoding.py    인코딩 판별·변환 (원본 FUN_140010f48 로직)
  search.py      찾기/바꾸기 문자열 로직 (UI와 분리)
  linenumbers.py 줄 번호 여백 (Text 명령을 가로채 편집·스크롤 때마다 다시 그림)
  ime.py         한글 등 IME 조합 문자열을 커서 위치에 본문 글꼴로 표시 (Windows)
  settings.py    설정 저장/불러오기
  resources.py   MUI에서 가져온 한국어 문자열
  themes.py      테마(색·글꼴·아이콘), 글꼴 등록, 제목 표시줄 색
  fonts/         IBM Plex Sans KR, Noto Sans KR (OFL, 라이선스 파일 포함)
  assets/        테마별 아이콘 (.ico, .png)
tests/           단위 테스트 + 실제 Tk 창을 띄우는 스모크 테스트
tools/make_icons.py    아이콘 다시 만들기 (Pillow 필요, 개발용)
tools/subset_fonts.py  글꼴에서 필요한 글자만 남기기 (fontTools 필요, 개발용)
web/             웹 버전 (index.html, style.css, js/app.js · encoding.js · search.js · markdown.js, tests/)
.github/workflows/pages.yml  웹 버전 테스트 + GitHub Pages 배포
design/          디자인 문서(DESIGN.md), 시안 HTML, 아이콘 SVG 원본
docs/ANALYSIS.md 분석 결과와 근거
```

## 나만의 기능 추가하기

1. `app.py`의 `NotepadApp`에 `cmd_내기능` 메서드를 추가한다.
2. `_build_menus`에서 `self._menu_item(메뉴, "이름(&K)", self.cmd_내기능, "Ctrl+K")`로 메뉴에 연결한다.
3. 단축키는 `_on_control_key`의 `table`에 `(ord("K"), False): self.cmd_내기능`을 추가한다.
   (Ctrl 조합은 가상 키 코드로 처리하므로 한글 입력 상태나 Caps Lock에서도 동작한다.)
4. UI와 무관한 로직은 `search.py`처럼 별도 모듈로 빼고 `tests/`에 테스트를 추가한다.

## 실행 파일(.exe) 만들기

설치 없이 실행되는 exe 파일 하나(`dist\PyNotepad.exe`, 약 18 MB)를 만든다. PyInstaller 6.22.3, Python 3.14에서 확인했다.

```powershell
pip install pyinstaller==6.22.3
python -m PyInstaller --noconfirm --clean --onefile --windowed --name PyNotepad `
  --icon "C:/WORK-Claude/Notepad/pynotepad/assets/icon-paper.ico" `
  --add-data "C:/WORK-Claude/Notepad/pynotepad/fonts;pynotepad/fonts" `
  --add-data "C:/WORK-Claude/Notepad/pynotepad/assets;pynotepad/assets" `
  --specpath build --distpath dist --workpath build notepad.pyw
```

- `--add-data` 경로는 절대 경로로 쓴다. `--specpath build`를 쓰면 상대 경로가 `build\` 기준으로 풀려서 글꼴을 찾지 못한다.
- exe는 실행할 때마다 임시 폴더에 압축을 풀기 때문에 창이 뜨기까지 1~2초 걸린다.
- `pynotepad/fonts/`의 글꼴은 크기를 줄인 버전이다(한글 11,172자·자모, 영문, 기호만 남김. 원본 17 MB → 12 MB).
  원본 글꼴에서 다시 만들려면: `pip install fonttools` 후 `python tools/subset_fonts.py <원본 글꼴 폴더>`.
  빠진 글자(한자 등)는 Windows의 다른 글꼴로 대신 표시된다.

## 테스트

```powershell
python -m unittest discover -s tests -t .
```
