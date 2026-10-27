"""UI strings taken verbatim from C:\\Windows\\System32\\ko-KR\\notepad.exe.mui (see docs/ANALYSIS.md)."""

APP_NAME = "메모장"
TITLE_FORMAT = "{dirty}{name} - Windows 메모장"
UNTITLED = "제목 없음"

# Status bar (the position label is translated; the original shows " Ln %d, Col %d")
STATUS_POSITION = " 줄 {line}, 열 {col}"
STATUS_ZOOM = " {zoom}%"
LINE_ENDING_LABELS = {
    "\r\n": " Windows (CRLF)",
    "\n": " Unix (LF)",
    "\r": " Macintosh (CR)",
}

# Messages ("%%" in the original is the file name)
MSG_CANNOT_OPEN = "{name} 파일을 열 수 없습니다.\n\n지정한 드라이브에 디스크가 있는지 확인하십시오."
MSG_NOT_FOUND_CREATE = "{name} 파일을 찾을 수 없습니다.\n\n새 파일을 만드시겠습니까?"
MSG_SAVE_CHANGES = "변경 내용을 {name}에 저장하시겠습니까?"
MSG_TEXT_NOT_FOUND = '"{text}"을(를) 찾을 수 없습니다.'
MSG_FILE_TOO_LARGE = "{name} 파일이 너무 커서 메모장에서 열 수 없습니다.\n\n다른 편집기를 사용하여 파일을 편집하십시오."
MSG_CANNOT_CREATE = "{name} 파일을 만들 수 없습니다.\n\n경로와 파일 이름이 올바른지 확인하십시오."
MSG_ACCESS_DENIED = "{name}\n이 파일을 열 수 있는 권한이 없습니다. 사용 권한에 대해서는 파일의 소유자나 관리자에게 문의하십시오."
MSG_ANSI_LOSS = (
    "{name}\n이 파일에는 ANSI로 인코딩된 문서로 저장하는 경우 손실될 유니코드 포맷 문자가 포함되어 있습니다. "
    "유니코드 정보를 보존하려면 [취소]를 클릭한 다음 인코딩 드롭다운 목록에서 유니코드 옵션 중 하나를 선택하십시오. "
    "계속하시겠습니까?"
)
MSG_LINE_OUT_OF_RANGE = "줄 번호가 전체 줄 수를 넘습니다."
MSG_GOTO_TITLE = "메모장 - 줄 이동"

# File dialog filters
FILTER_TEXT = ("텍스트 문서(*.txt)", "*.txt")
FILTER_MARKDOWN = ("마크다운 문서(*.md)", "*.md *.markdown")
FILTER_ALL = ("모든 파일", "*.*")

# Buttons
BTN_SAVE = "저장(S)"
BTN_DONT_SAVE = "저장 안 함(N)"
BTN_CANCEL = "취소"
BTN_OK = "확인"

# Links observed in the command handler (FUN_14000da7c)
GOOGLE_SEARCH_URL = "https://www.google.com/search?q={query}"
