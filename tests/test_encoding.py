import unittest

from pynotepad import encoding as E


class DetectTests(unittest.TestCase):
    def test_boms(self):
        self.assertEqual(E.detect(b"\xef\xbb\xbfabc"), E.UTF8_BOM)
        self.assertEqual(E.detect(b"\xff\xfea\x00"), E.UTF16_LE)
        self.assertEqual(E.detect(b"\xfe\xff\x00a"), E.UTF16_BE)

    def test_utf8_without_bom(self):
        self.assertEqual(E.detect("안녕하세요".encode("utf-8")), E.UTF8)

    def test_plain_ascii_is_utf8(self):
        # ASCII is valid UTF-8, so notepad reports UTF-8 rather than ANSI.
        self.assertEqual(E.detect(b"hello world"), E.UTF8)

    def test_ansi_korean(self):
        self.assertEqual(E.detect("한글 텍스트 파일입니다".encode("cp949")), E.ANSI)

    def test_utf16_le_without_bom(self):
        data = ("This is a fairly long UTF-16 little endian text without a BOM. " * 3).encode("utf-16-le")
        self.assertEqual(E.detect(data), E.UTF16_LE)


class RoundTripTests(unittest.TestCase):
    def test_round_trip_all_encodings(self):
        text = "첫 줄\n둘째 줄 ABC\n"
        for enc in E.CHOICES:
            for eol in ("\r\n", "\n", "\r"):
                with self.subTest(enc=enc, eol=repr(eol)):
                    data = E.encode(text, enc, eol)
                    doc = E.decode(data)
                    self.assertEqual(doc.text, text)
                    self.assertEqual(doc.line_ending, eol)
                    if enc != E.ANSI:  # ANSI Korean bytes are not valid UTF-8, but ASCII-only would be
                        self.assertEqual(doc.encoding, enc)

    def test_nul_becomes_space(self):
        self.assertEqual(E.decode(b"a\x00b").text, "a b")

    def test_line_ending_default_is_crlf(self):
        self.assertEqual(E.decode(b"single line").line_ending, "\r\n")

    def test_ansi_loss(self):
        self.assertFalse(E.loses_data_as_ansi("한글"))
        self.assertTrue(E.loses_data_as_ansi("emoji 😀"))


if __name__ == "__main__":
    unittest.main()
