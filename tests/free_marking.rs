// Bỏ dấu tự do (free_marking): phím dấu tìm mục tiêu trong cả âm tiết.
use vikey_engine::vnengine::{type_word, type_word_ex, Method, VnEngine};

fn free(keys: &str) -> String {
    type_word_ex(keys, true, false, Method::Telex, true)
}
fn free_vni(keys: &str) -> String {
    type_word_ex(keys, true, false, Method::Vni, true)
}

#[test]
fn mark_after_final_consonant() {
    for (keys, want) in [
        ("dend", "đen"),
        ("dendf", "đèn"),
        ("dauad", "đâu"),
        ("tienge", "tiêng"),
        ("tienges", "tiếng"),
        ("khongo", "không"),
        ("hoco", "hôc"),
        ("duongwd", "đương"),
        ("duongdw", "đương"),
    ] {
        assert_eq!(free(keys), want, "keys={keys:?}");
    }
}

#[test]
fn old_style_keys_still_work() {
    for (keys, want) in [
        ("ddeens", "đến"),
        ("vieejt", "việt"),
        ("dduwowngf", "đường"),
        ("nguoiwf", "người"),
        ("toans", "toán"),
        ("giuwx", "giữ"),
        ("quocos", "quốc"),
    ] {
        assert_eq!(free(keys), want, "keys={keys:?}");
    }
}

#[test]
fn vni_free_marking() {
    for (keys, want) in [("den9", "đen"), ("khong6", "không"), ("duong972", "đường")] {
        assert_eq!(free_vni(keys), want, "keys={keys:?}");
    }
}

/// Gõ lặp phím dấu để hoàn tác - chỉ khi phím nằm NGAY SAU phím đã tạo dấu.
#[test]
fn repeat_key_undoes_only_when_adjacent() {
    assert_eq!(free("bietee"), "biete");
    assert_eq!(free("dendd"), "dend");
    assert_eq!(free("ddd"), "dd");
    // hoàn tác từ xa sẽ nuốt mất một chữ đã gõ -> không nhận
    assert_eq!(free("banana"), "banana");
    assert_eq!(free("dadad"), "dadad");
}

/// Kiểm tra chính tả vẫn giữ nguyên từ tiếng Anh hay dùng.
#[test]
fn english_words_survive_spell_check() {
    for w in ["windows", "sudo", "status", "added", "dodge", "google", "keyboard", "render", "header"] {
        assert_eq!(free(w), w, "keys={w:?}");
    }
}

/// Tắt free_marking -> hành vi y hệt trước (khớp bản Python).
#[test]
fn disabled_keeps_old_behaviour() {
    for keys in ["dend", "tienge", "khongo", "dauad", "banana", "data"] {
        assert_eq!(
            type_word_ex(keys, true, false, Method::Telex, false),
            type_word(keys, true, false, Method::Telex),
            "keys={keys:?}"
        );
    }
    assert_eq!(type_word("dend", true, false, Method::Telex), "dend");
}

/// Backspace dựng lại từ dãy phím thô nên vẫn đúng ở chế độ tự do.
#[test]
fn backspace_rebuilds() {
    let mut e = VnEngine::new(true, false, Method::Telex);
    e.free_marking = true;
    for k in "dendf".chars() {
        e.process_key(k);
    }
    assert_eq!(e.text(), "đèn");
    let mut trace = vec![e.text()];
    while e.backspace() {
        trace.push(e.text());
    }
    assert_eq!(trace, ["đèn", "đen", "den", "de", "d", ""]);
    assert!(e.is_empty());
}
