// keyval.rs - Chuyển keysym -> ký tự unicode (tương đương ibus_keyval_to_unicode
// cho phần cần dùng: ASCII, Latin-1, bàn phím số, keysym unicode).

pub fn keyval_to_char(kv: u32) -> char {
    match kv {
        0x20..=0x7E => kv as u8 as char,
        0xA0..=0xFF => char::from_u32(kv).unwrap_or('\0'),
        0xFF80 => ' ',                        // KP_Space
        0xFFAA => '*',
        0xFFAB => '+',
        0xFFAC => ',',
        0xFFAD => '-',
        0xFFAE => '.',
        0xFFAF => '/',
        0xFFB0..=0xFFB9 => (b'0' + (kv - 0xFFB0) as u8) as char, // KP_0..KP_9
        0xFFBD => '=',
        0x0100_0000..=0x0110_FFFF => char::from_u32(kv - 0x0100_0000).unwrap_or('\0'),
        _ => '\0',
    }
}
