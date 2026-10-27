# Windows 메모장 분석 결과 (REA + Ghidra)

- 대상: `C:\Windows\System32\notepad.exe` 10.0.26100.8875 (x64, SHA-256 `468ffe12…4577e`)
- 리소스: `C:\Windows\System32\ko-KR\notepad.exe.mui` (SHA-256 `16ab5f4b…76be0`)
- 도구: REA 6.5.0, Ghidra 12.1.4 (PDB 심볼 없음 → 함수 이름은 `FUN_<주소>`)

각 항목의 근거 유형: **관찰** = 바이너리/리소스에서 직접 확인, **추론** = 관찰을 바탕으로 한 해석.

## 1. UI 구조 (MUI 리소스, 관찰)

`inspect_pe_resources`(Evidence `ev_fddbbe4e…`)가 보고한 오프셋을 직접 디코딩했다.

| 메뉴 | 항목 (명령 ID) |
|---|---|
| 파일 | 새로 만들기(1) Ctrl+N · 새 창(8) Ctrl+Shift+N · 열기(2) Ctrl+O · 저장(3) Ctrl+S · 다른 이름으로 저장(4) Ctrl+Shift+S · 페이지 설정(5) · 인쇄(6) Ctrl+P · 끝내기(7) |
| 편집 | 실행 취소(16) Ctrl+Z · 잘라내기(768) · 복사(769) · 붙여넣기(770) · 삭제(771) Del · Bing으로 검색(28) Ctrl+E · 찾기(21) Ctrl+F · 다음 찾기(22) F3 · 이전 찾기(29) Shift+F3 · 바꾸기(23) Ctrl+H · 이동(24) Ctrl+G · 모두 선택(25) Ctrl+A · 시간/날짜(26) F5 |
| 서식 | 자동 줄 바꿈(32) · 글꼴(33) |
| 보기 | 확대(34) Ctrl++ · 축소(35) Ctrl+- · 기본값 복원(36) Ctrl+0 · 상태 표시줄(27) |
| 도움말 | 도움말 보기(64) F1 · 피드백 보내기(66) · 메모장 정보(65) |

추가 단축키(가속기 테이블): Ctrl+W = 끝내기, Ctrl+Insert = 복사, Alt+Backspace = 실행 취소, 숫자패드 +/-/0도 확대·축소·복원.

대화 상자: 찾기(찾을 내용 / 단어 단위로 / 대/소문자 구분 / 주위에 배치 / 방향 위로·아래로), 바꾸기(+ 바꿀 내용 / 바꾸기 / 모두 바꾸기), 줄 이동(줄 번호), 페이지 설정(용지·방향·여백·머리글 `&f`·바닥글 `&p 페이지`), 저장 대화 상자의 인코딩 콤보.

상태 표시줄 문자열: ` Ln %d, Col %d`, ` %d%%`, ` Windows (CRLF)` / ` Unix (LF)` / ` Macintosh (CR)`, 인코딩 이름 `ANSI`·`UTF-16 LE`·`UTF-16 BE`·`UTF-8`·`UTF-8(BOM)`.

제목: `%1%2 - Windows 메모장`, 새 문서 이름 `제목 없음`. 주요 메시지는 `pynotepad/resources.py`에 원문 그대로 옮겼다.

## 2. 동작 (Ghidra 디컴파일)

### 파일 열기 — `FUN_140010f48` (관찰, Evidence `ev_7dd947fc…`)
- 1 GiB(`0x40000000`) 이상 파일은 거부.
- 인코딩 판별 순서: `EF BB BF` → UTF-8(BOM) · `FF FE` → UTF-16 LE · `FE FF` → UTF-16 BE · 그 외 `IsTextUnicode` 성공(단, 100바이트 미만에서 통계적 판정만 맞으면 무시) → UTF-16 LE · UTF-8로 유효하면 UTF-8 · 아니면 ANSI(시스템 코드 페이지).
- 내부 인코딩 ID: 1=ANSI, 2=UTF-16 LE, 3=UTF-16 BE, 4=UTF-8(BOM), 5=UTF-8, 6=GB18030.
- 본문의 NUL 문자는 공백으로 치환.
- 본문이 대소문자 구분으로 `.LOG`로 시작하면 캐럿을 끝으로 옮기고 시간/날짜 기록을 추가.
- 열기 성공 시 `SHAddToRecentDocs`로 최근 문서에 등록.

### 시간/날짜 — `FUN_140010580` (관찰, Evidence `ev_01d9b50f…`)
- `GetTimeFormatW(TIME_NOSECONDS)` + `" "` + `GetDateFormatW(DATE_SHORTDATE)`.
- `.LOG` 모드에서는 앞뒤에 `\r\n`을 붙임.

### 명령 처리 — `FUN_14000da7c` (관찰, Evidence `ev_f743c299…`)
- 확대/축소: 현재 배율 ±10%, 범위 10%~500%, 기본값 복원 = 100%.
- 글꼴: `ChooseFontW`로 고르고 포인트 크기를 저장.
- 끝내기: `WM_CLOSE` 전송(저장 확인을 거침).
- 도움말 = `https://go.microsoft.com/fwlink/?LinkId=834783`, 피드백 = `feedback-hub://?tabid=2&contextid=1010`, 정보 = `ShellAboutW`.
- 잘라내기/복사/삭제/Bing 검색은 선택 영역이 있을 때만 동작.
- Bing으로 검색은 에디트 컨트롤에 메시지 `0x150F`를 보내 처리한다. 실제 URL은 바이너리에 없다(**추론**: 시스템 에디트 컨트롤이 bing.com 검색을 연다).

### 설정 저장 (문자열 관찰, 레지스트리 `HKCU\Software\Microsoft\Notepad`)
`lfFaceName`, `iPointSize`, `fWrap`, `StatusBar`, `szHeader`, `szTrailer`, `iMargin*`, `iWindowPos*`, `fReverse`, `fWrapAround`, `fMatchCase`, `searchString`, `replaceString`, `iDefaultEncoding`, `fSaveWindowPositions`.

### 인코딩 사전 검사 — `FUN_14000ca10` (관찰, Evidence `ev_3ee405d5…`)
저장 대화 상자 등에서 쓰이며, 파일 앞 1024바이트로 위와 같은 판별을 한다.

## 3. 재현 시 설계 선택 (원본과 다른 점)

| 항목 | 원본 | 재현 |
|---|---|---|
| 설정 저장 위치 | 레지스트리 | `%APPDATA%\PyNotepad\settings.json` (진짜 메모장 설정을 건드리지 않기 위해), 키 이름은 원본과 동일 |
| 실행 취소 | 1단계(EDIT 컨트롤) | 여러 단계 (Tk Text) |
| 저장 인코딩 선택 | 저장 대화 상자 안 콤보 | 파일 선택 후 인코딩 선택 창 |
| 인쇄 / 페이지 설정 | GDI 직접 인쇄, 머리글/바닥글 | Windows 셸 인쇄 동사 사용, 페이지 설정 미구현 |
| 줄 끝 판별 | 상태 표시줄 문자열만 확인됨(판별 코드 미추적) | 파일에서 가장 먼저 나오는 줄 끝 형식을 채택하고 저장 시 유지 (**추론**) |
| Bing 검색 | 에디트 컨트롤 내장 기능 | 메뉴 이름을 "Google로 검색"으로 바꾸고 `https://www.google.com/search?q=<선택 텍스트>`를 연다 |
