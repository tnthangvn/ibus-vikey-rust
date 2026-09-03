// So khớp 1:1 với bộ gõ Python gốc qua fixture sinh sẵn (15k+ trường hợp).
use vikey_engine::vnengine::{type_word, Method, VnEngine};

#[test]
fn matches_python_reference() {
    let data = std::fs::read_to_string(concat!(env!("CARGO_MANIFEST_DIR"), "/fixtures/engine_fixture.json"))
        .expect("fixture");
    let v: serde_json::Value = serde_json::from_str(&data).unwrap();
    let mut n = 0;
    for case in v["cases"].as_array().unwrap() {
        let w = case[0].as_str().unwrap();
        let method = Method::from_str(case[1].as_str().unwrap());
        let sc = case[2].as_bool().unwrap();
        let mt = case[3].as_bool().unwrap();
        let expect = case[4].as_str().unwrap();
        let got = type_word(w, sc, mt, method);
        assert_eq!(got, expect, "keys={:?} method={:?} sc={} mt={}", w, method, sc, mt);
        n += 1;
    }
    assert!(n > 10000);
}

#[test]
fn backspace_matches_python_reference() {
    let data = std::fs::read_to_string(concat!(env!("CARGO_MANIFEST_DIR"), "/fixtures/engine_fixture.json"))
        .expect("fixture");
    let v: serde_json::Value = serde_json::from_str(&data).unwrap();
    for case in v["backspace"].as_array().unwrap() {
        let w = case[0].as_str().unwrap();
        let trace: Vec<&str> = case[1].as_array().unwrap().iter().map(|x| x.as_str().unwrap()).collect();
        let mut e = VnEngine::new(true, false, Method::Telex);
        for k in w.chars() {
            e.process_key(k);
        }
        let mut got = vec![e.text()];
        while e.backspace() {
            got.push(e.text());
        }
        assert_eq!(got, trace, "keys={:?}", w);
        assert!(e.is_empty());
    }
}
