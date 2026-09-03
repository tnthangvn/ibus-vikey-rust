#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vnengine.py - Bộ gõ tiếng Việt kiểu Telex, thuần Python, không phụ thuộc IBus.

Nguyên lý: mỗi "từ" đang gõ là một dãy phím thô (entries). Mỗi phím hoặc
tạo ra một chữ cái (lit), hoặc được "tiêu thụ" làm phím bỏ dấu (mod), hoặc
đã bị hoàn tác khi gõ lặp (undone: "ass" -> "as", "tesst" -> "test").

Toàn bộ từ được dựng lại từ dãy phím thô mỗi lần bấm Backspace, nên trạng thái
luôn nhất quán và không bao giờ cần gửi Backspace giả tới ứng dụng.

Kiểm tra chính tả: nếu từ hiện tại không thể là một âm tiết tiếng Việt hợp lệ
(vd. "windows", "status", "data") thì trả về nguyên dãy phím thô, giống tính
năng "khôi phục phím với từ sai" của Unikey. Nhờ vậy gõ lệnh trong terminal
ít bị biến dạng hơn.
"""

import unicodedata

VOWELS = frozenset("aeiouy")

TONE_NONE, TONE_SAC, TONE_HUYEN, TONE_HOI, TONE_NGA, TONE_NANG = range(6)
_TONE_COMBINING = {
    TONE_SAC: "́",
    TONE_HUYEN: "̀",
    TONE_HOI: "̉",
    TONE_NGA: "̃",
    TONE_NANG: "̣",
}

_MARKED = {
    ("a", "hat"): "â",
    ("a", "breve"): "ă",
    ("e", "hat"): "ê",
    ("o", "hat"): "ô",
    ("o", "horn"): "ơ",
    ("u", "horn"): "ư",
    ("d", "stroke"): "đ",
}

TELEX_TONES = {"s": TONE_SAC, "f": TONE_HUYEN, "r": TONE_HOI, "x": TONE_NGA, "j": TONE_NANG}
TELEX_HAT = frozenset("aeo")
VNI_TONES = {"1": TONE_SAC, "2": TONE_HUYEN, "3": TONE_HOI, "4": TONE_NGA, "5": TONE_NANG}

METHODS = ("telex", "vni", "both")   # kiểu gõ: Telex | VNI | Telex + VNI cùng lúc

# Phụ âm đầu hợp lệ (mọi tiền tố của chúng cũng nằm trong tập này).
ONSETS = frozenset(
    [
        "", "b", "c", "ch", "d", "đ", "g", "gh", "gi", "h", "k", "kh", "l", "m",
        "n", "ng", "ngh", "nh", "p", "ph", "q", "qu", "r", "s", "t", "th", "tr",
        "v", "x",
    ]
)
# Phụ âm cuối hợp lệ.
CODAS = frozenset(["c", "ch", "m", "n", "ng", "nh", "p", "t"])
# Các cụm nguyên âm hợp lệ, viết theo chữ gốc (bỏ dấu mũ/móc) để việc kiểm tra
# khoan dung với trạng thái trung gian ("tie" -> "tiê", "uo" -> "ươ").
_NUCLEI = [
    "a", "e", "i", "o", "u", "y",
    "ai", "ao", "au", "ay", "eo", "eu", "ia", "ie", "iu", "oa", "oe", "oi", "oo",
    "ua", "ue", "ui", "uo", "uu", "uy", "ye",
    "ieu", "yeu", "oai", "oao", "oay", "oeo", "uay", "uoi", "uou", "uya", "uye",
    "uyu",
]
_NUCLEUS_PREFIXES = frozenset(n[:i] for n in _NUCLEI for i in range(1, len(n) + 1))


def compose_char(base, mark, tone, upper):
    """Ghép chữ cái gốc + dấu mũ/móc + dấu thanh thành ký tự Unicode dựng sẵn."""
    ch = _MARKED.get((base, mark), base)
    if tone and base in VOWELS:
        ch = unicodedata.normalize("NFC", ch + _TONE_COMBINING[tone])
    return ch.upper() if upper else ch


class _Char(object):
    __slots__ = ("base", "upper", "mark", "frozen", "mark_entry", "standalone", "pending_pair", "revert")

    def __init__(self, base, upper, mark="", frozen=False, mark_entry=None, standalone=False, revert=False):
        self.base = base            # chữ cái gốc, thường
        self.upper = upper          # có viết hoa không
        self.mark = mark            # '', 'hat', 'breve', 'horn', 'stroke'
        self.frozen = frozen        # sinh ra từ thao tác hoàn tác -> không bỏ dấu nữa
        self.mark_entry = mark_entry  # chỉ số phím đã tạo dấu mũ/móc
        self.standalone = standalone  # ư sinh từ phím w đứng một mình
        self.pending_pair = False   # 'uơ' (huơ, thuở) sẽ thành 'ươ' nếu gõ tiếp
        self.revert = revert        # chữ chèn vào khi gõ lặp phím dấu ("ass" -> "as")

    def is_vowel(self):
        return self.base in VOWELS


LIT, MOD, UNDONE = "lit", "mod", "undone"


class VnEngine(object):
    """Bộ gõ Telex cho MỘT từ đang soạn."""

    def __init__(self, spell_check=True, modern_tone=False, method="telex"):
        self.spell_check = spell_check    # khôi phục phím thô với từ sai chính tả
        self.modern_tone = modern_tone    # hoà/khoẻ/thuý thay vì hòa/khỏe/thúy
        self.method = method if method in METHODS else "telex"
        self.reset()

    @property
    def telex(self):
        return self.method in ("telex", "both")

    @property
    def vni(self):
        return self.method in ("vni", "both")

    def accepts_digit(self):
        """Phím số có phải phím bỏ dấu (VNI) khi đang soạn từ không?"""
        return self.vni and not self.is_empty()

    # ------------------------------------------------------------------ API
    def reset(self):
        self.entries = []   # [key, state]
        self.chars = []     # [_Char]
        self.tone = TONE_NONE
        self.tone_entry = None

    def is_empty(self):
        return not self.entries

    def process_key(self, key):
        """Nhận một ký tự chữ cái ASCII (giữ nguyên hoa/thường), hoặc chữ số (VNI)."""
        self.entries.append([key, LIT])
        self._apply(len(self.entries) - 1)

    def backspace(self):
        """Xoá phím cuối, dựng lại từ. Trả về False nếu không còn gì để xoá."""
        if not self.entries:
            return False
        entries = [e[0] for e in self.entries[:-1]]
        self.reset()
        for k in entries:
            self.process_key(k)
        return True

    def raw(self):
        """Dãy phím thô (đã bỏ các phím bị hoàn tác)."""
        return "".join(k for k, st in self.entries if st != UNDONE)

    def composed(self):
        """Từ đã bỏ dấu, không kiểm tra chính tả."""
        if not self.chars:
            return ""
        ti = self._tone_index() if self.tone else None
        return "".join(
            compose_char(c.base, c.mark, self.tone if i == ti else TONE_NONE, c.upper)
            for i, c in enumerate(self.chars)
        )

    def text(self):
        """Chuỗi hiển thị/commit."""
        if not self.entries:
            return ""
        if self.spell_check and not self.is_valid():
            return self.raw()
        return self.composed()

    # ------------------------------------------------------------ xử lý phím
    def _apply(self, i):
        key = self.entries[i][0]
        k = key.lower()
        ok = False
        if k.isdigit():
            if self.vni:
                ok = self._apply_vni(i, k)
        elif self.telex:
            ok = self._apply_telex(i, k)
        if not ok:
            self._append_literal(i)

    def _apply_telex(self, i, k):
        if k in TELEX_TONES:
            return self._apply_tone(i, TELEX_TONES[k])
        if k == "z":
            return self._remove_tone(i)
        if k == "d":
            return self._apply_stroke(i)
        if k == "w":
            self._apply_horn(i, allow_breve=True, standalone=True)
            return True
        if k in TELEX_HAT:
            return self._apply_hat(i, (k,))
        return False

    def _apply_vni(self, i, k):
        """VNI: 1-5 dấu thanh, 6 mũ (â ê ô), 7 móc (ơ ư), 8 trăng (ă), 9 đ, 0 xoá dấu."""
        if k in VNI_TONES:
            return self._apply_tone(i, VNI_TONES[k])
        if k == "0":
            return self._remove_tone(i)
        if k == "6":
            return self._apply_hat(i, ("a", "e", "o"))
        if k == "7":
            return self._apply_horn(i, allow_breve=False, standalone=False)
        if k == "8":
            return self._apply_horn(i, allow_breve=True, standalone=False, only_breve=True)
        if k == "9":
            return self._apply_stroke(i)
        return False

    def _remove_tone(self, i):
        if not self.tone:
            return False
        self.tone = TONE_NONE
        self.tone_entry = None
        self.entries[i][1] = MOD
        return True

    def _append_literal(self, i, frozen=False):
        key = self.entries[i][0]
        self.entries[i][1] = LIT
        self._resolve_pending_uo()
        self.chars.append(_Char(key.lower(), key.isupper(), frozen=frozen, revert=frozen))

    def _resolve_pending_uo(self):
        """'huơ'/'thuơ' + thêm chữ -> 'hươ'/'thươ' (hương, thương, hươu)."""
        if len(self.chars) < 2:
            return
        o, u = self.chars[-1], self.chars[-2]
        if o.pending_pair and u.base == "u" and u.mark == "" and not u.frozen:
            u.mark = "horn"
            u.mark_entry = o.mark_entry
        o.pending_pair = False

    def _last_vowel(self):
        for j in range(len(self.chars) - 1, -1, -1):
            if self.chars[j].is_vowel():
                return j
        return None

    def _is_qu_u(self, j):
        return j == 1 and self.chars[0].base == "q" and self.chars[1].base == "u"

    # --- dấu thanh: s f r x j
    def _apply_tone(self, i, tone):
        if self._last_vowel() is None:
            return False
        if self.tone == tone:
            # gõ lặp phím dấu -> bỏ dấu, chèn phím đó như chữ thường
            if self.tone_entry is not None:
                self.entries[self.tone_entry][1] = UNDONE
            self.tone = TONE_NONE
            self.tone_entry = None
            self._append_literal(i, frozen=True)
            return True
        self.tone = tone
        self.tone_entry = i
        self.entries[i][1] = MOD
        return True

    # --- dấu mũ: aa ee oo (Telex) / 6 (VNI)
    def _apply_hat(self, i, bases):
        j = self._last_vowel()
        if j is None or j != len(self.chars) - 1:
            return False   # chưa có nguyên âm, hoặc đã có phụ âm cuối -> chữ thường
        c = self.chars[j]
        if c.base not in bases or c.frozen:
            return False
        if c.mark == "":
            c.mark = "hat"
            c.mark_entry = i
            self.entries[i][1] = MOD
            return True
        if c.mark == "hat" and c.mark_entry is not None:
            self.entries[c.mark_entry][1] = UNDONE
            c.mark = ""
            c.mark_entry = None
            c.frozen = True
            self._append_literal(i, frozen=True)
            return True
        return False

    # --- dấu móc / trăng: w
    def _raw_cluster(self):
        """Chỉ số cụm nguyên âm cuối cùng (liên tiếp), kể cả u của 'qu'."""
        j = self._last_vowel()
        if j is None:
            return []
        k = j
        while k > 0 and self.chars[k - 1].is_vowel():
            k -= 1
        return list(range(k, j + 1))

    def _apply_horn(self, i, allow_breve, standalone, only_breve=False):
        """Telex w: ă ơ ư ươ, w đứng một mình -> ư.  VNI 7: ơ ư ươ.  VNI 8: ă.
        Trả về True nếu đã xử lý (kể cả ư đứng một mình / hoàn tác), False -> chữ thường."""
        key = self.entries[i][0]
        kl = key.lower()
        chars = self.chars
        cluster = self._raw_cluster()
        targets = ("a",) if only_breve else (("a", "o", "u") if allow_breve else ("o", "u"))
        if cluster:
            has_coda = cluster[-1] < len(chars) - 1
            # tìm mục tiêu, duyệt từ cuối cụm về đầu
            for k in reversed(cluster):
                c = chars[k]
                if c.mark != "" or c.frozen or c.base not in targets:
                    continue
                if self._is_qu_u(k):
                    continue
                prev = chars[k - 1] if k > 0 and k - 1 >= cluster[0] and not self._is_qu_u(k - 1) else None
                if c.base == "a" and prev is not None and prev.base == "u" and prev.mark == "horn":
                    break  # 'ưa' + w -> hoàn tác chứ không thành 'ưă'
                # uo + w -> ươ (dương, người, rượu)
                if c.base == "o" and prev is not None and prev.base == "u" and prev.mark in ("", "horn"):
                    c.mark = "horn"
                    c.mark_entry = i
                    if prev.mark == "" and not prev.frozen:
                        onset = "".join(ch.base for ch in chars[: k - 1])
                        if onset in ("h", "th", "kh") and k == cluster[-1] and not has_coda:
                            # huơ, thuở: tạm giữ 'uơ'; gõ tiếp sẽ thành 'ươ' (hương, thương)
                            c.pending_pair = True
                        else:
                            prev.mark = "horn"
                            prev.mark_entry = i
                    self.entries[i][1] = MOD
                    return True
                # ua + w -> ưa (mưa, chưa)
                if (c.base == "a" and not only_breve and prev is not None and prev.base == "u"
                        and prev.mark == "" and not prev.frozen):
                    prev.mark = "horn"
                    prev.mark_entry = i
                    self.entries[i][1] = MOD
                    return True
                c.mark = "breve" if c.base == "a" else "horn"
                c.mark_entry = i
                self.entries[i][1] = MOD
                return True
            # không còn mục tiêu: hoàn tác nếu trong cụm có dấu do CHÍNH phím này tạo ra
            w_marked = [
                k for k in cluster
                if chars[k].mark in ("horn", "breve")
                and chars[k].mark_entry is not None
                and self.entries[chars[k].mark_entry][0].lower() == kl
            ]
            if w_marked:
                me = chars[w_marked[-1]].mark_entry
                if chars[w_marked[-1]].standalone and w_marked[-1] == cluster[-1]:
                    del chars[w_marked[-1]]
                else:
                    for ch in chars:
                        if ch.mark_entry == me:
                            ch.mark = ""
                            ch.mark_entry = None
                            ch.frozen = True
                self.entries[me][1] = UNDONE
                self._append_literal(i, frozen=True)
                return True
        if not standalone:
            return False
        # không có mục tiêu: w đứng một mình -> ư
        self.entries[i][1] = LIT
        self._resolve_pending_uo()
        chars.append(_Char("u", key.isupper(), mark="horn", mark_entry=i, standalone=True))
        return True

    # --- đ: dd
    def _apply_stroke(self, i):
        if not self.chars:
            return False
        c0 = self.chars[0]
        if c0.base != "d":
            return False
        if c0.mark == "" and not c0.frozen and all(ch.is_vowel() for ch in self.chars[1:]):
            c0.mark = "stroke"
            c0.mark_entry = i
            self.entries[i][1] = MOD
            return True
        if c0.mark == "stroke" and c0.mark_entry is not None and len(self.chars) == 1:
            self.entries[c0.mark_entry][1] = UNDONE
            c0.mark = ""
            c0.mark_entry = None
            c0.frozen = True
            self._append_literal(i, frozen=True)
            return True
        return False

    # ------------------------------------------------------- vị trí dấu thanh
    def _vowel_cluster(self):
        """Trả về danh sách chỉ số cụm nguyên âm chính (bỏ u của 'qu', i của 'gi')."""
        chars = self.chars
        n = len(chars)
        excl = set()
        if n >= 2 and chars[0].base == "q" and chars[1].base == "u" and chars[1].mark == "":
            excl.add(1)
        if (
            n >= 3 and chars[0].base == "g" and chars[1].base == "i"
            and chars[1].mark == "" and chars[2].is_vowel()
        ):
            excl.add(1)
        vowels = [k for k, c in enumerate(chars) if c.is_vowel() and k not in excl]
        if not vowels:
            return []
        # cụm nguyên âm cuối cùng (âm tiết đang gõ)
        cluster = [vowels[-1]]
        for k in reversed(vowels[:-1]):
            if k == cluster[0] - 1:
                cluster.insert(0, k)
            else:
                break
        return cluster

    def _tone_index(self):
        cluster = self._vowel_cluster()
        if not cluster:
            return None
        chars = self.chars
        if len(cluster) == 1:
            return cluster[0]
        marked = [k for k in cluster if chars[k].mark]
        if marked:
            return marked[-1]
        has_coda = cluster[-1] < len(chars) - 1
        if len(cluster) >= 3 or has_coda:
            return cluster[1]
        if self.modern_tone:
            pair = (chars[cluster[0]].base, chars[cluster[1]].base)
            if pair in (("o", "a"), ("o", "e"), ("u", "y")):
                return cluster[1]
        return cluster[0]

    # ---------------------------------------------------- kiểm tra chính tả
    def is_valid(self):
        """Từ hiện tại có thể là (tiền tố của) một âm tiết tiếng Việt không?

        Phần sau chữ cái do người dùng cố ý chèn bằng cách gõ lặp phím dấu
        ("ddaayss" -> "đâys") không bị xét, vì đó là ý muốn rõ ràng của người gõ.
        """
        chars = self.chars
        for k, c in enumerate(chars):
            if c.revert:
                chars = chars[:k]
                break
        n = len(chars)
        if n == 0:
            return True
        bases = "".join(c.base for c in chars)
        if any(b in "fjwz" or b.isdigit() for b in bases):
            return False
        # phụ âm đầu
        if bases[0] == "q":
            if n == 1:
                return True
            if bases[1] != "u" or chars[1].mark != "":
                return False
            i = 2
        elif bases.startswith("gi") and n >= 3 and bases[2] in VOWELS:
            i = 2
        else:
            i = 0
            while i < n and bases[i] not in VOWELS:
                i += 1
            onset = "".join(compose_char(c.base, c.mark, 0, False) for c in chars[:i])
            if onset not in ONSETS:
                return False
        # nguyên âm
        j = i
        while j < n and bases[j] in VOWELS:
            j += 1
        nucleus = bases[i:j]
        if nucleus and nucleus not in _NUCLEUS_PREFIXES:
            return False
        # phụ âm cuối
        coda = bases[j:]
        if not coda:
            return True
        if not nucleus:
            return False
        if any(b in VOWELS for b in coda):
            return False
        if any(c.mark for c in chars[j:]):
            return False
        return coda in CODAS


def type_word(word, **kw):
    """Tiện ích: gõ một chuỗi phím và trả về kết quả (kw: spell_check, modern_tone, method)."""
    e = VnEngine(**kw)
    for k in word:
        e.process_key(k)
    return e.text()


if __name__ == "__main__":
    import sys

    for w in sys.argv[1:]:
        print(w, "->", type_word(w))
