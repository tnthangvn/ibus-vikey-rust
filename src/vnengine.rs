// vnengine.rs - Bộ gõ tiếng Việt (Telex/VNI) - port 1:1 từ vnengine.py.
//
// Nguyên lý: mỗi "từ" đang gõ là một dãy phím thô (entries). Mỗi phím hoặc tạo
// ra một chữ cái (Lit), hoặc được "tiêu thụ" làm phím bỏ dấu (Mod), hoặc đã bị
// hoàn tác khi gõ lặp (Undone: "ass" -> "as"). Backspace = bỏ phím cuối và dựng
// lại từ từ đầu, nên không bao giờ cần gửi Backspace giả tới ứng dụng.

use unicode_normalization::UnicodeNormalization;

pub const TONE_NONE: u8 = 0;

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Mark {
    None,
    Hat,
    Breve,
    Horn,
    Stroke,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Method {
    Telex,
    Vni,
    Both,
}

impl Method {
    pub fn from_str(s: &str) -> Method {
        match s {
            "vni" => Method::Vni,
            "both" => Method::Both,
            _ => Method::Telex,
        }
    }
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum EntryState {
    Lit,
    Mod,
    Undone,
}

#[derive(Clone)]
struct Entry {
    key: char,
    state: EntryState,
}

#[derive(Clone)]
struct VChar {
    base: char, // chữ cái gốc, thường
    upper: bool,
    mark: Mark,
    frozen: bool,            // sinh ra từ thao tác hoàn tác -> không bỏ dấu nữa
    mark_entry: Option<usize>, // chỉ số phím đã tạo dấu mũ/móc
    standalone: bool,        // ư sinh từ phím w đứng một mình
    pending_pair: bool,      // 'uơ' (huơ, thuở) sẽ thành 'ươ' nếu gõ tiếp
    revert: bool,            // chữ chèn khi gõ lặp phím dấu ("ass" -> "as")
}

impl VChar {
    fn new(base: char, upper: bool) -> VChar {
        VChar {
            base,
            upper,
            mark: Mark::None,
            frozen: false,
            mark_entry: None,
            standalone: false,
            pending_pair: false,
            revert: false,
        }
    }
    fn is_vowel(&self) -> bool {
        matches!(self.base, 'a' | 'e' | 'i' | 'o' | 'u' | 'y')
    }
}

fn is_vowel_ch(c: char) -> bool {
    matches!(c, 'a' | 'e' | 'i' | 'o' | 'u' | 'y')
}

fn marked_char(base: char, mark: Mark) -> char {
    match (base, mark) {
        ('a', Mark::Hat) => 'â',
        ('a', Mark::Breve) => 'ă',
        ('e', Mark::Hat) => 'ê',
        ('o', Mark::Hat) => 'ô',
        ('o', Mark::Horn) => 'ơ',
        ('u', Mark::Horn) => 'ư',
        ('d', Mark::Stroke) => 'đ',
        _ => base,
    }
}

const TONE_COMBINING: [char; 6] = ['\0', '\u{0301}', '\u{0300}', '\u{0309}', '\u{0303}', '\u{0323}'];

pub fn compose_char(base: char, mark: Mark, tone: u8, upper: bool) -> char {
    let mut ch = marked_char(base, mark);
    if tone != TONE_NONE && is_vowel_ch(base) {
        let s: String = [ch, TONE_COMBINING[tone as usize]].iter().collect();
        ch = s.nfc().next().unwrap_or(ch);
    }
    if upper {
        ch.to_uppercase().next().unwrap_or(ch)
    } else {
        ch
    }
}

fn telex_tone(k: char) -> Option<u8> {
    match k {
        's' => Some(1),
        'f' => Some(2),
        'r' => Some(3),
        'x' => Some(4),
        'j' => Some(5),
        _ => None,
    }
}

fn vni_tone(k: char) -> Option<u8> {
    match k {
        '1' => Some(1),
        '2' => Some(2),
        '3' => Some(3),
        '4' => Some(4),
        '5' => Some(5),
        _ => None,
    }
}

const ONSETS: [&str; 29] = [
    "", "b", "c", "ch", "d", "đ", "g", "gh", "gi", "h", "k", "kh", "l", "m", "n", "ng", "ngh",
    "nh", "p", "ph", "q", "qu", "r", "s", "t", "th", "tr", "v", "x",
];
const CODAS: [&str; 8] = ["c", "ch", "m", "n", "ng", "nh", "p", "t"];
// Các cụm nguyên âm hợp lệ theo chữ gốc (mọi tiền tố đều được chấp nhận khi kiểm tra)
const NUCLEI: [&str; 39] = [
    "a", "e", "i", "o", "u", "y", "ai", "ao", "au", "ay", "eo", "eu", "ia", "ie", "iu", "oa",
    "oe", "oi", "oo", "ua", "ue", "ui", "uo", "uu", "uy", "ye", "ieu", "yeu", "oai", "oao",
    "oay", "oeo", "uay", "uoi", "uou", "uya", "uye", "uyu", "oa",
];

fn nucleus_ok(n: &str) -> bool {
    NUCLEI.iter().any(|x| x.starts_with(n))
}

pub struct VnEngine {
    pub spell_check: bool,
    pub modern_tone: bool,
    /// Bỏ dấu tự do: phím dấu (dd, aa/ee/oo) tìm mục tiêu trong cả âm tiết,
    /// không bắt buộc đứng ngay sau chữ cái gốc ("dend" -> đen, "tienge" -> tiêng).
    pub free_marking: bool,
    pub method: Method,
    entries: Vec<Entry>,
    chars: Vec<VChar>,
    tone: u8,
    tone_entry: Option<usize>,
}

impl VnEngine {
    pub fn new(spell_check: bool, modern_tone: bool, method: Method) -> VnEngine {
        VnEngine {
            spell_check,
            modern_tone,
            free_marking: false,
            method,
            entries: Vec::new(),
            chars: Vec::new(),
            tone: TONE_NONE,
            tone_entry: None,
        }
    }

    pub fn reset(&mut self) {
        self.entries.clear();
        self.chars.clear();
        self.tone = TONE_NONE;
        self.tone_entry = None;
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    fn telex(&self) -> bool {
        matches!(self.method, Method::Telex | Method::Both)
    }
    fn vni(&self) -> bool {
        matches!(self.method, Method::Vni | Method::Both)
    }

    /// Phím số có phải phím bỏ dấu (VNI) khi đang soạn từ không?
    pub fn accepts_digit(&self) -> bool {
        self.vni() && !self.is_empty()
    }

    /// Nhận một chữ cái ASCII (giữ nguyên hoa/thường), hoặc chữ số (VNI).
    pub fn process_key(&mut self, key: char) {
        self.entries.push(Entry { key, state: EntryState::Lit });
        self.apply(self.entries.len() - 1);
    }

    /// Xoá phím cuối, dựng lại từ. false nếu không còn gì để xoá.
    pub fn backspace(&mut self) -> bool {
        if self.entries.is_empty() {
            return false;
        }
        let keys: Vec<char> = self.entries[..self.entries.len() - 1].iter().map(|e| e.key).collect();
        self.reset();
        for k in keys {
            self.process_key(k);
        }
        true
    }

    /// Dãy phím thô (đã bỏ các phím bị hoàn tác).
    pub fn raw(&self) -> String {
        self.entries
            .iter()
            .filter(|e| e.state != EntryState::Undone)
            .map(|e| e.key)
            .collect()
    }

    /// Từ đã bỏ dấu, không kiểm tra chính tả.
    pub fn composed(&self) -> String {
        if self.chars.is_empty() {
            return String::new();
        }
        let ti = if self.tone != TONE_NONE { self.tone_index() } else { None };
        self.chars
            .iter()
            .enumerate()
            .map(|(i, c)| {
                let t = if Some(i) == ti { self.tone } else { TONE_NONE };
                compose_char(c.base, c.mark, t, c.upper)
            })
            .collect()
    }

    /// Chuỗi hiển thị/commit (khôi phục phím thô với từ sai chính tả).
    pub fn text(&self) -> String {
        if self.entries.is_empty() {
            return String::new();
        }
        if self.spell_check && !self.is_valid() {
            return self.raw();
        }
        self.composed()
    }

    // ------------------------------------------------------------ xử lý phím
    fn apply(&mut self, i: usize) {
        let key = self.entries[i].key;
        let k = key.to_ascii_lowercase();
        let ok = if k.is_ascii_digit() {
            self.vni() && self.apply_vni(i, k)
        } else if self.telex() {
            self.apply_telex(i, k)
        } else {
            false
        };
        if !ok {
            self.append_literal(i, false);
        }
    }

    fn apply_telex(&mut self, i: usize, k: char) -> bool {
        if let Some(t) = telex_tone(k) {
            return self.apply_tone(i, t);
        }
        match k {
            'z' => self.remove_tone(i),
            'd' => self.apply_stroke(i),
            'w' => {
                self.apply_horn(i, true, true, false);
                true
            }
            'a' | 'e' | 'o' => self.apply_hat(i, &[k]),
            _ => false,
        }
    }

    /// VNI: 1-5 dấu thanh, 6 mũ, 7 móc, 8 trăng, 9 đ, 0 xoá dấu.
    fn apply_vni(&mut self, i: usize, k: char) -> bool {
        if let Some(t) = vni_tone(k) {
            return self.apply_tone(i, t);
        }
        match k {
            '0' => self.remove_tone(i),
            '6' => self.apply_hat(i, &['a', 'e', 'o']),
            '7' => self.apply_horn(i, false, false, false),
            '8' => self.apply_horn(i, true, false, true),
            '9' => self.apply_stroke(i),
            _ => false,
        }
    }

    fn remove_tone(&mut self, i: usize) -> bool {
        if self.tone == TONE_NONE {
            return false;
        }
        self.tone = TONE_NONE;
        self.tone_entry = None;
        self.entries[i].state = EntryState::Mod;
        true
    }

    fn append_literal(&mut self, i: usize, frozen: bool) {
        let key = self.entries[i].key;
        self.entries[i].state = EntryState::Lit;
        self.resolve_pending_uo();
        let mut c = VChar::new(key.to_ascii_lowercase(), key.is_ascii_uppercase());
        c.frozen = frozen;
        c.revert = frozen;
        self.chars.push(c);
    }

    /// 'huơ'/'thuơ' + thêm chữ -> 'hươ'/'thươ' (hương, thương, hươu).
    fn resolve_pending_uo(&mut self) {
        let n = self.chars.len();
        if n < 2 {
            return;
        }
        let pending = self.chars[n - 1].pending_pair;
        let me = self.chars[n - 1].mark_entry;
        if pending {
            let u = &self.chars[n - 2];
            if u.base == 'u' && u.mark == Mark::None && !u.frozen {
                self.chars[n - 2].mark = Mark::Horn;
                self.chars[n - 2].mark_entry = me;
            }
        }
        self.chars[n - 1].pending_pair = false;
    }

    fn last_vowel(&self) -> Option<usize> {
        (0..self.chars.len()).rev().find(|&j| self.chars[j].is_vowel())
    }

    fn is_qu_u(&self, j: usize) -> bool {
        j == 1 && self.chars[0].base == 'q' && self.chars[1].base == 'u'
    }

    // --- dấu thanh
    fn apply_tone(&mut self, i: usize, tone: u8) -> bool {
        if self.last_vowel().is_none() {
            return false;
        }
        if self.tone == tone {
            // gõ lặp phím dấu -> bỏ dấu, chèn phím đó như chữ thường
            if let Some(te) = self.tone_entry {
                self.entries[te].state = EntryState::Undone;
            }
            self.tone = TONE_NONE;
            self.tone_entry = None;
            self.append_literal(i, true);
            return true;
        }
        self.tone = tone;
        self.tone_entry = Some(i);
        self.entries[i].state = EntryState::Mod;
        true
    }

    // --- dấu mũ: aa ee oo (Telex) / 6 (VNI)
    fn apply_hat(&mut self, i: usize, bases: &[char]) -> bool {
        if self.free_marking {
            return self.apply_hat_free(i, bases);
        }
        let j = match self.last_vowel() {
            Some(j) => j,
            None => return false,
        };
        if j != self.chars.len() - 1 {
            return false; // đã có phụ âm cuối -> chữ thường
        }
        let c = &self.chars[j];
        if !bases.contains(&c.base) || c.frozen {
            return false;
        }
        if c.mark == Mark::None {
            self.chars[j].mark = Mark::Hat;
            self.chars[j].mark_entry = Some(i);
            self.entries[i].state = EntryState::Mod;
            return true;
        }
        if c.mark == Mark::Hat {
            if let Some(me) = c.mark_entry {
                self.entries[me].state = EntryState::Undone;
                self.chars[j].mark = Mark::None;
                self.chars[j].mark_entry = None;
                self.chars[j].frozen = true;
                self.append_literal(i, true);
                return true;
            }
        }
        false
    }

    /// Bỏ dấu tự do: quét cả cụm nguyên âm (kể cả khi đã có phụ âm cuối),
    /// giống cách `apply_horn` đã làm cho w/7/8.
    fn apply_hat_free(&mut self, i: usize, bases: &[char]) -> bool {
        let cluster = self.raw_cluster();
        if cluster.is_empty() {
            return false;
        }
        // ưu tiên đặt dấu: nguyên âm khớp gần cuối cụm nhất, chưa có dấu
        for &k in cluster.iter().rev() {
            let c = &self.chars[k];
            if c.mark != Mark::None || c.frozen || !bases.contains(&c.base) {
                continue;
            }
            if self.is_qu_u(k) {
                continue;
            }
            self.chars[k].mark = Mark::Hat;
            self.chars[k].mark_entry = Some(i);
            self.entries[i].state = EntryState::Mod;
            return true;
        }
        // Không còn mục tiêu -> gõ lặp để hoàn tác ("bietee" -> biete).
        // Chỉ nhận khi phím dấu vừa gõ nằm ngay sau phím đã tạo dấu; hoàn tác
        // từ xa sẽ nuốt mất một chữ đã gõ ("banana" -> "banna").
        for &k in cluster.iter().rev() {
            let c = self.chars[k].clone();
            if c.mark != Mark::Hat || !bases.contains(&c.base) {
                continue;
            }
            if c.mark_entry != Some(i.wrapping_sub(1)) {
                continue;
            }
            if let Some(me) = c.mark_entry {
                self.entries[me].state = EntryState::Undone;
                self.chars[k].mark = Mark::None;
                self.chars[k].mark_entry = None;
                self.chars[k].frozen = true;
                self.append_literal(i, true);
                return true;
            }
        }
        false
    }

    /// Chỉ số cụm nguyên âm cuối cùng (liên tiếp), kể cả u của 'qu'.
    fn raw_cluster(&self) -> Vec<usize> {
        let j = match self.last_vowel() {
            Some(j) => j,
            None => return vec![],
        };
        let mut k = j;
        while k > 0 && self.chars[k - 1].is_vowel() {
            k -= 1;
        }
        (k..=j).collect()
    }

    // --- dấu móc / trăng: w (Telex), 7/8 (VNI)
    fn apply_horn(&mut self, i: usize, allow_breve: bool, standalone: bool, only_breve: bool) -> bool {
        let key = self.entries[i].key;
        let kl = key.to_ascii_lowercase();
        let cluster = self.raw_cluster();
        if !cluster.is_empty() {
            let has_coda = *cluster.last().unwrap() < self.chars.len() - 1;
            // tìm mục tiêu, duyệt từ cuối cụm về đầu
            for &k in cluster.iter().rev() {
                let c = self.chars[k].clone();
                let target_ok = if only_breve {
                    c.base == 'a'
                } else if allow_breve {
                    matches!(c.base, 'a' | 'o' | 'u')
                } else {
                    matches!(c.base, 'o' | 'u')
                };
                if c.mark != Mark::None || c.frozen || !target_ok {
                    continue;
                }
                if self.is_qu_u(k) {
                    continue;
                }
                let prev_idx = if k > 0 && k - 1 >= cluster[0] && !self.is_qu_u(k - 1) {
                    Some(k - 1)
                } else {
                    None
                };
                let prev = prev_idx.map(|p| self.chars[p].clone());
                if c.base == 'a' {
                    if let Some(ref p) = prev {
                        if p.base == 'u' && p.mark == Mark::Horn {
                            break; // 'ưa' + w -> hoàn tác chứ không thành 'ưă'
                        }
                    }
                }
                // uo + w -> ươ (dương, người, rượu)
                if c.base == 'o' {
                    if let (Some(pi), Some(ref p)) = (prev_idx, prev.as_ref().map(|x| x.clone())) {
                        if p.base == 'u' && (p.mark == Mark::None || p.mark == Mark::Horn) {
                            self.chars[k].mark = Mark::Horn;
                            self.chars[k].mark_entry = Some(i);
                            if p.mark == Mark::None && !p.frozen {
                                let onset: String = self.chars[..k - 1].iter().map(|ch| ch.base).collect();
                                if (onset == "h" || onset == "th" || onset == "kh")
                                    && k == *cluster.last().unwrap()
                                    && !has_coda
                                {
                                    // huơ, thuở: tạm giữ 'uơ'; gõ tiếp sẽ thành 'ươ'
                                    self.chars[k].pending_pair = true;
                                } else {
                                    self.chars[pi].mark = Mark::Horn;
                                    self.chars[pi].mark_entry = Some(i);
                                }
                            }
                            self.entries[i].state = EntryState::Mod;
                            return true;
                        }
                    }
                }
                // ua + w -> ưa (mưa, chưa)
                if c.base == 'a' && !only_breve {
                    if let (Some(pi), Some(ref p)) = (prev_idx, prev.as_ref()) {
                        if p.base == 'u' && p.mark == Mark::None && !p.frozen {
                            self.chars[pi].mark = Mark::Horn;
                            self.chars[pi].mark_entry = Some(i);
                            self.entries[i].state = EntryState::Mod;
                            return true;
                        }
                    }
                }
                self.chars[k].mark = if c.base == 'a' { Mark::Breve } else { Mark::Horn };
                self.chars[k].mark_entry = Some(i);
                self.entries[i].state = EntryState::Mod;
                return true;
            }
            // không còn mục tiêu: hoàn tác nếu trong cụm có dấu do CHÍNH phím này tạo ra
            let w_marked: Vec<usize> = cluster
                .iter()
                .cloned()
                .filter(|&k| {
                    let c = &self.chars[k];
                    (c.mark == Mark::Horn || c.mark == Mark::Breve)
                        && c.mark_entry
                            .map(|me| self.entries[me].key.to_ascii_lowercase() == kl)
                            .unwrap_or(false)
                })
                .collect();
            if let Some(&lastm) = w_marked.last() {
                let me = self.chars[lastm].mark_entry.unwrap();
                if self.chars[lastm].standalone && lastm == *cluster.last().unwrap() {
                    self.chars.remove(lastm);
                } else {
                    for ch in self.chars.iter_mut() {
                        if ch.mark_entry == Some(me) {
                            ch.mark = Mark::None;
                            ch.mark_entry = None;
                            ch.frozen = true;
                        }
                    }
                }
                self.entries[me].state = EntryState::Undone;
                self.append_literal(i, true);
                return true;
            }
        }
        if !standalone {
            return false;
        }
        // không có mục tiêu: w đứng một mình -> ư
        self.entries[i].state = EntryState::Lit;
        self.resolve_pending_uo();
        let mut c = VChar::new('u', key.is_ascii_uppercase());
        c.mark = Mark::Horn;
        c.mark_entry = Some(i);
        c.standalone = true;
        self.chars.push(c);
        true
    }

    // --- đ: dd (Telex) / 9 (VNI)
    fn apply_stroke(&mut self, i: usize) -> bool {
        if self.chars.is_empty() {
            return false;
        }
        let c0 = self.chars[0].clone();
        if c0.base != 'd' {
            return false;
        }
        // Âm tiết tiếng Việt không có 'd' ở phụ âm cuối, nên khi bỏ dấu tự do
        // mọi phím 'd' sau chữ đầu đều là phím tạo đ ("dend" -> đen).
        let reachable = self.free_marking || self.chars[1..].iter().all(|c| c.is_vowel());
        if c0.mark == Mark::None && !c0.frozen && reachable {
            self.chars[0].mark = Mark::Stroke;
            self.chars[0].mark_entry = Some(i);
            self.entries[i].state = EntryState::Mod;
            return true;
        }
        // Hoàn tác: lối cũ chỉ khi từ mới có mỗi 'đ'; bỏ dấu tự do thì phím 'd'
        // phải nằm ngay sau phím đã tạo đ, tránh nuốt chữ ở "dadad".
        let undoable = if self.free_marking {
            c0.mark_entry == Some(i.wrapping_sub(1))
        } else {
            self.chars.len() == 1
        };
        if c0.mark == Mark::Stroke && c0.mark_entry.is_some() && undoable {
            self.entries[c0.mark_entry.unwrap()].state = EntryState::Undone;
            self.chars[0].mark = Mark::None;
            self.chars[0].mark_entry = None;
            self.chars[0].frozen = true;
            self.append_literal(i, true);
            return true;
        }
        false
    }

    // ------------------------------------------------------- vị trí dấu thanh
    /// Cụm nguyên âm chính (bỏ u của 'qu', i của 'gi'), lấy cụm cuối cùng.
    fn vowel_cluster(&self) -> Vec<usize> {
        let chars = &self.chars;
        let n = chars.len();
        let mut excl: Option<usize> = None;
        if n >= 2 && chars[0].base == 'q' && chars[1].base == 'u' && chars[1].mark == Mark::None {
            excl = Some(1);
        }
        if n >= 3
            && chars[0].base == 'g'
            && chars[1].base == 'i'
            && chars[1].mark == Mark::None
            && chars[2].is_vowel()
        {
            excl = Some(1);
        }
        let vowels: Vec<usize> = (0..n)
            .filter(|&k| chars[k].is_vowel() && Some(k) != excl)
            .collect();
        if vowels.is_empty() {
            return vec![];
        }
        // cụm nguyên âm cuối cùng (âm tiết đang gõ)
        let mut cluster = vec![*vowels.last().unwrap()];
        for &k in vowels[..vowels.len() - 1].iter().rev() {
            if k + 1 == cluster[0] {
                cluster.insert(0, k);
            } else {
                break;
            }
        }
        cluster
    }

    fn tone_index(&self) -> Option<usize> {
        let cluster = self.vowel_cluster();
        if cluster.is_empty() {
            return None;
        }
        let chars = &self.chars;
        if cluster.len() == 1 {
            return Some(cluster[0]);
        }
        let marked: Vec<usize> = cluster.iter().cloned().filter(|&k| chars[k].mark != Mark::None).collect();
        if let Some(&m) = marked.last() {
            return Some(m);
        }
        let has_coda = *cluster.last().unwrap() < chars.len() - 1;
        if cluster.len() >= 3 || has_coda {
            return Some(cluster[1]);
        }
        if self.modern_tone {
            let pair = (chars[cluster[0]].base, chars[cluster[1]].base);
            if pair == ('o', 'a') || pair == ('o', 'e') || pair == ('u', 'y') {
                return Some(cluster[1]);
            }
        }
        Some(cluster[0])
    }

    // ---------------------------------------------------- kiểm tra chính tả
    /// Từ hiện tại có thể là (tiền tố của) một âm tiết tiếng Việt không?
    /// Phần sau chữ do người dùng cố ý chèn bằng gõ lặp phím dấu không bị xét.
    pub fn is_valid(&self) -> bool {
        let mut chars: &[VChar] = &self.chars;
        for (k, c) in self.chars.iter().enumerate() {
            if c.revert {
                chars = &self.chars[..k];
                break;
            }
        }
        let n = chars.len();
        if n == 0 {
            return true;
        }
        let bases: Vec<char> = chars.iter().map(|c| c.base).collect();
        if bases.iter().any(|&b| matches!(b, 'f' | 'j' | 'w' | 'z') || b.is_ascii_digit()) {
            return false;
        }
        // phụ âm đầu
        let mut i;
        if bases[0] == 'q' {
            if n == 1 {
                return true;
            }
            if bases[1] != 'u' || chars[1].mark != Mark::None {
                return false;
            }
            i = 2;
        } else if n >= 3 && bases[0] == 'g' && bases[1] == 'i' && is_vowel_ch(bases[2]) {
            i = 2;
        } else {
            i = 0;
            while i < n && !is_vowel_ch(bases[i]) {
                i += 1;
            }
            let onset: String = chars[..i].iter().map(|c| marked_char(c.base, c.mark)).collect();
            if !ONSETS.contains(&onset.as_str()) {
                return false;
            }
        }
        // nguyên âm
        let mut j = i;
        while j < n && is_vowel_ch(bases[j]) {
            j += 1;
        }
        let nucleus: String = bases[i..j].iter().collect();
        if !nucleus.is_empty() && !nucleus_ok(&nucleus) {
            return false;
        }
        // phụ âm cuối
        if j == n {
            return true;
        }
        if nucleus.is_empty() {
            return false;
        }
        if bases[j..].iter().any(|&b| is_vowel_ch(b)) {
            return false;
        }
        if chars[j..].iter().any(|c| c.mark != Mark::None) {
            return false;
        }
        let coda: String = bases[j..].iter().collect();
        CODAS.contains(&coda.as_str())
    }
}

/// Tiện ích cho test/CLI: gõ một chuỗi phím và trả về kết quả.
pub fn type_word(word: &str, spell_check: bool, modern_tone: bool, method: Method) -> String {
    type_word_ex(word, spell_check, modern_tone, method, false)
}

/// Như `type_word` nhưng chọn được chế độ bỏ dấu tự do.
pub fn type_word_ex(
    word: &str,
    spell_check: bool,
    modern_tone: bool,
    method: Method,
    free_marking: bool,
) -> String {
    let mut e = VnEngine::new(spell_check, modern_tone, method);
    e.free_marking = free_marking;
    for k in word.chars() {
        e.process_key(k);
    }
    e.text()
}
