# -*- coding: utf-8 -*-
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vikey"))

from vnengine import VnEngine, type_word  # noqa: E402

CASES = [
    # cơ bản
    ("vieets", "viết"), ("tieesng", "tiếng"), ("Vieejt", "Việt"), ("ddaay", "đây"),
    ("nguowif", "người"), ("duowngf", "dường"), ("thuongw", "thương"), ("toans", "toán"),
    ("hoaf", "hòa"), ("khoer", "khỏe"), ("thuys", "thúy"), ("quas", "quá"), ("gias", "giá"),
    ("gif", "gì"), ("khuyar", "khuỷa"), ("ruwowuj", "rượu"), ("muwa", "mưa"), ("muaw", "mưa"),
    ("cuwus", "cứu"), ("xuaan", "xuân"), ("hoawcj", "hoặc"), ("ddi", "đi"), ("tuwj", "tự"),
    ("Ddaij", "Đại"), ("TIEENGS", "TIẾNG"), ("quyeenf", "quyền"), ("nghieeng", "nghiêng"),
    ("uwowcs", "ước"), ("yeeu", "yêu"), ("aw", "ă"), ("aws", "ắ"), ("w", "ư"), ("tw", "tư"),
    ("dduwowngf", "đường"), ("nguyeenx", "nguyễn"), ("khoong", "không"), ("chuwax", "chữa"),
    ("oaif", "oài"), ("thuyr", "thủy"), ("ngoawcj", "ngoặc"), ("quawn", "quăn"), ("queen", "quên"),
    ("giuwx", "giữ"), ("mowis", "mới"), ("ddoocj", "độc"), ("ddocj", "đọc"), ("gioongs", "giống"),
    ("giuwowngf", "giường"), ("khuyur", "khuỷu"), ("ngoafi", "ngoài"), ("tuoiw", "tươi"),
    ("tuowir", "tưởi"), ("Hoof", "Hồ"), ("Chis", "Chí"), ("Minh", "Minh"), ("xax", "xã"),
    ("hooij", "hội"), ("chur", "chủ"), ("nghixa", "nghĩa"), ("Thawng", "Thăng"),
    # huơ / thuở / hương / thương / hươu
    ("thuowr", "thuở"), ("huow", "huơ"), ("huowng", "hương"), ("thuowng", "thương"),
    ("huowu", "hươu"), ("khuowcs", "khước"), ("thuowrng", "thưởng"),
    # bỏ dấu tự do (dấu thanh sau phụ âm cuối), w sau phụ âm cuối
    ("hoangf", "hoàng"), ("duongw", "dương"), ("thangw", "thăng"),
    # xoá dấu
    ("asz", "a"), ("hoafz", "hoa"),
    # gõ lặp phím để lấy chữ gốc
    ("ass", "as"), ("tesst", "test"), ("aaa", "aa"), ("ddd", "dd"), ("ww", "w"), ("ooo", "oo"),
    ("eee", "ee"), ("toool", "tool"),
    # từ tiếng Anh / lệnh terminal: khôi phục phím thô
    ("windows", "windows"), ("status", "status"), ("data", "data"), ("tools", "tools"),
    ("book", "book"), ("sudo", "sudo"), ("ls", "ls"), ("banana", "banana"), ("apt", "apt"),
    ("install", "install"), ("git", "git"), ("commit", "commit"), ("python", "python"),
    ("docker", "docker"), ("grep", "grep"), ("echo", "echo"), ("cd", "cd"), ("mkdir", "mkdir"),
    ("pwd", "pwd"), ("systemctl", "systemctl"), ("restart", "restart"), ("update", "update"),
    ("upgrade", "upgrade"), ("firefox", "firefox"), ("chrome", "chrome"), ("npm", "npm"),
    ("vim", "vim"), ("nano", "nano"), ("ssh", "ssh"), ("rsync", "rsync"), ("kill", "kill"),
    ("localhost", "localhost"), ("world", "world"), ("hello", "hello"),
]


class TestTelex(unittest.TestCase):
    def test_words(self):
        for keys, expect in CASES:
            with self.subTest(keys=keys):
                self.assertEqual(type_word(keys), expect)

    def test_modern_tone(self):
        self.assertEqual(type_word("hoaf", modern_tone=True), "hoà")
        self.assertEqual(type_word("khoer", modern_tone=True), "khoẻ")
        self.assertEqual(type_word("thuys", modern_tone=True), "thuý")
        self.assertEqual(type_word("hoangf", modern_tone=True), "hoàng")

    def test_no_spell_check(self):
        self.assertEqual(type_word("windows", spell_check=False), "ưindớ")
        self.assertEqual(type_word("tools", spell_check=False), "tốl")

    def test_backspace(self):
        e = VnEngine()
        for k in "vieets":
            e.process_key(k)
        self.assertEqual(e.text(), "viết")
        self.assertTrue(e.backspace())
        self.assertEqual(e.text(), "viêt")
        self.assertTrue(e.backspace())
        self.assertEqual(e.text(), "viê")
        self.assertTrue(e.backspace())
        self.assertEqual(e.text(), "vie")
        for _ in range(3):
            self.assertTrue(e.backspace())
        self.assertEqual(e.text(), "")
        self.assertTrue(e.is_empty())
        self.assertFalse(e.backspace())

    def test_backspace_restores_from_invalid(self):
        e = VnEngine()
        for k in "tools":
            e.process_key(k)
        self.assertEqual(e.text(), "tools")
        e.backspace()  # "tool"
        self.assertEqual(e.text(), "tool")
        e.backspace()  # "too" -> tô
        self.assertEqual(e.text(), "tô")

    def test_raw_after_revert(self):
        e = VnEngine()
        for k in "ass":
            e.process_key(k)
        self.assertEqual(e.raw(), "as")

    def test_reset(self):
        e = VnEngine()
        for k in "abc":
            e.process_key(k)
        e.reset()
        self.assertEqual(e.text(), "")
        self.assertTrue(e.is_empty())

    def test_uppercase_w(self):
        self.assertEqual(type_word("W"), "Ư")
        self.assertEqual(type_word("TUWJ"), "TỰ")
        self.assertEqual(type_word("DDoocj"), "Độc")


if __name__ == "__main__":
    unittest.main()
