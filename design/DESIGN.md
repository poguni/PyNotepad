# PyNotepad 디자인 — 테마 A · 종이 / 테마 B · 슬레이트

기능은 지금과 똑같이 두고 겉모습만 바꾼다. 시안 A와 B를 둘 다 구현해서 **메뉴 막대 오른쪽 끝의 테마 드롭다운**에서 고르게 한다.
구현: `pynotepad/themes.py` (2026-10-18).

- 시안 화면: [concept-a-paper.html](concept-a-paper.html), [concept-b-slate.html](concept-b-slate.html)
  (브라우저로 열기. 글꼴은 Google Fonts에서 불러오므로 인터넷 연결 필요)
- 아이콘 원본: [icons/icon-a-paper.svg](icons/icon-a-paper.svg), [icons/icon-b-slate.svg](icons/icon-b-slate.svg)
- 캔버스(세 시안 비교, 시안 C 포함): https://claude.ai/artifact/5ytn2d9U7BgRP6NgdoFQUt

## 1. 공통 구조

두 테마는 같은 뼈대를 쓰고 색·글꼴·문서 이름 표시 방식만 다르다.

```
┌ 제목 표시줄 (Windows가 그림: 색만 바꿀 수 있음) ────────────┐
│ 메뉴 막대  파일(F) 편집(E) 서식(O) 보기(V) [미리 보기][테마: 종이 ▾] │
│ 문서 줄    A: "제목 없음  [수정됨]"   B: 문서 탭 "제목 없음 ●" │
│ ┌줄 번호┐ 편집 영역 (현재 줄 강조, 선택 색)                 │
│ 상태 표시줄            줄 3, 열 30 │ 100% │ CRLF │ UTF-8      │
└──────────────────────────────────────────────────────┘
```

- **문서 줄(새로 추가)**: 제목 표시줄 글꼴은 바꿀 수 없으므로, 문서 이름을 테마 UI 글꼴로 한 번 더 보여 준다.
  저장하지 않은 변경이 있으면 A는 "수정됨" 칩, B는 탭 옆의 점으로 표시한다.
- 메뉴 막대·편집 메뉴·오른쪽 클릭 메뉴의 항목, 단축키, 동작은 바뀌지 않는다.
- 상태 표시줄의 위치 표시는 `Ln 3, Col 30` → `줄 3, 열 30`으로 한글화한다.

## 2. 색 토큰

| 토큰 | 쓰이는 곳 | A · 종이 | B · 슬레이트 |
|---|---|---|---|
| `caption` | 제목 표시줄 바탕 (DWM 캡션 색) | `#F3F0EA` | `#1E232B` |
| `caption_text` | 제목 표시줄 글자 | `#4A463E` | `#C9CFD9` |
| `chrome` | 메뉴 막대, 상태 표시줄 바탕 | `#F3F0EA` | `#1E232B` |
| `chrome_text` | 메뉴 막대 글자 | `#2B2924` | `#E9ECF1` |
| `chrome_line` | 메뉴 막대·상태 표시줄 경계선 | `#E4DFD5` | (없음) |
| `menu_active` | 열린 메뉴 막대 항목 바탕 | `#E4DFD4` | `#3A414D` |
| `doc_bg` | 문서 줄 바탕 | `#FBFAF7` | `#2A303A` (탭 줄) |
| `tab_bg` | 문서 탭 바탕 | — | `#FFFFFF` |
| `editor_bg` | 편집 영역 바탕 | `#FFFEFB` | `#FFFFFF` |
| `text` | 본문 글자 | `#23211D` | `#1B2029` |
| `gutter_bg` | 줄 번호 여백 바탕 | `#F7F5F0` | `#F4F6F9` |
| `gutter_line` | 줄 번호 여백 경계선 | `#ECE8DF` | `#E6EAF0` |
| `line_num` | 줄 번호 | `#ADA697` | `#9AA3B2` |
| `line_num_current` | 현재 줄 번호 (굵게) | `#23211D` | `#1B2029` |
| `current_line` | 현재 줄 바탕 | `#F4F1EA` | `#F1F5FC` |
| `selection` | 선택 영역 바탕 | `#CFE6E3` | `#CFE0FA` |
| `accent` | 포인트 (수정됨 표시, 아이콘) | `#0F6E6E` | `#2F6FDB` |
| `accent_soft` | 포인트 연한 바탕 (수정됨 칩) | `#E3EFEE` | `#EAF1FD` |
| `popup_bg` | 드롭다운·오른쪽 클릭 메뉴 바탕 | `#FFFFFF` | `#FFFFFF` |
| `popup_hover_bg` | 메뉴 항목 강조 바탕 | `#E3EFEE` | `#1F5BC4` |
| `popup_hover_text` | 메뉴 항목 강조 글자 | `#0F6E6E` | `#FFFFFF` |
| `accel` | 메뉴의 단축키 글자 | `#8A8476` | `#7A8394` |
| `disabled` | 비활성 메뉴 항목 | `#B9B2A4` | `#A9B1BE` |
| `status_text` | 상태 표시줄 글자 | `#5B564C` | `#C3C9D3` |
| `status_sep` | 상태 표시줄 칸 구분선 | `#DDD7CB` | `#3A414D` |

## 3. 글꼴

| 용도 | A · 종이 | B · 슬레이트 |
|---|---|---|
| 메뉴 막대·메뉴·상태 표시줄 | IBM Plex Sans KR 15px / 500 (메뉴 항목 14.5px) | Noto Sans KR 15px / 500 |
| 문서 이름 | IBM Plex Sans KR 17px / 600 | Noto Sans KR 14px / 500 (탭) |
| 상태 표시줄 | 13px / 400 | 13px / 400 |
| 본문(편집 영역) | D2Coding (지금과 동일, 사용자가 서식 > 글꼴로 바꿀 수 있음) | 같음 |
| 제목 표시줄 | Windows 기본 (바꿀 수 없음) | 같음 |

- 두 UI 글꼴은 모두 SIL Open Font License라 앱에 함께 넣어 배포할 수 있다. 앱에는 한글·영문·기호만 남긴 축소판을 넣는다(`tools/subset_fonts.py`).
- `pynotepad/fonts/`에 글꼴 파일과 라이선스를 넣고, 시작할 때 `AddFontResourceExW(FR_PRIVATE)`로
  **이 앱에만** 등록한다. 시스템 글꼴 설치는 필요 없다.
- 글꼴을 찾지 못하면 맑은 고딕으로 대체한다.

## 4. 아이콘

| | A · 종이 | B · 슬레이트 |
|---|---|---|
| 모양 | 청록 둥근 사각형 위에 모서리를 접은 종이와 글줄 3개 | 파란 둥근 사각형 위에 윗부분이 묶인 메모지와 글줄 3개 |
| 원본 | `icons/icon-a-paper.svg` | `icons/icon-b-slate.svg` |

- `python tools/make_icons.py`가 16·24·32·48·64·256px 크기로 `pynotepad/assets/icon-<테마>.ico`와 `.png`를 만든다.
  작은 크기(16·24px)에서는 글줄 수를 줄이고 굵게 해서 뭉개지지 않게 한다.
- 창 아이콘(제목 표시줄, 작업 표시줄, 대화 상자)은 선택한 테마를 따라 바뀐다.
- 기본 아이콘(바로 가기 등에 지정할 하나): `pynotepad/assets/icon-paper.ico`

## 5. 테마 전환

- 메뉴 막대 오른쪽 끝의 **`테마: 종이 ▾`** 드롭다운에서 종이 / 슬레이트를 고른다. 바꾸면 창을 다시 열지 않고 바로 적용한다.
- 처음 실행할 때는 **종이**. 설정 파일(`settings.json`)에 `"theme": "paper" | "slate"`로 저장한다.
- 테마 정의는 위 색 토큰과 글꼴을 담은 데이터 하나(`THEMES`)로 모으고, 화면 각 부분은 그 데이터만 읽어서 칠한다.

## 6. Tk로 구현할 때의 제약

| 시안에서 | 실제 앱에서 |
|---|---|
| 제목 표시줄 글꼴 | 바꿀 수 없음. 바탕색·글자색만 `DwmSetWindowAttribute`(Windows 11)로 바꾼다. Windows 10에서는 기본색 유지 |
| 드롭다운 메뉴의 둥근 모서리·그림자 | Windows 11이 그려 주는 만큼만 적용된다. 색·글꼴·강조색은 그대로 적용 |
| 메뉴 항목 강조 바탕의 둥근 모서리 | 직사각형으로 칠해진다 |
| 문서 탭의 둥근 윗모서리 (B) | 직사각형 탭으로 그린다 |
| 스크롤바 | Windows 기본 스크롤바를 그대로 쓴다 (테마 색 없음. ttk 테마를 바꾸면 대화 상자 모양까지 바뀌어서 하지 않음) |
| 미리 보기 버튼 | `tk.Button`은 Windows에서 안쪽 여백이 커서 메뉴 막대가 높아지므로 `tk.Label`로 만든다 |

## 7. 확정된 결정

1. 기본 테마: **종이**
2. 기본 아이콘: **종이** (`icon-paper.ico`)
3. 상태 표시줄 위치 표시: **`줄 3, 열 30`** (원본 메모장의 `Ln 3, Col 30`을 한글화)
4. 테마 선택: 메뉴 막대 오른쪽 끝 드롭다운
