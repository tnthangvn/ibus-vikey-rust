// ibus_serde.rs - Dựng các cấu trúc IBus (IBusText, IBusProperty...) đúng wire-format:
//   Mọi đối tượng IBus là một STRUCT, hai trường đầu là tên lớp (s) và attachments
//   (a{sv}); khi nằm trong trường/đối số kiểu 'v' thì được bọc variant (zvariant
//   tự bọc khi đưa `Value` vào body hoặc `Value::new(...)` vào trường).
//   IBusText      = (sa{sv}sv)   : text, attr_list
//   IBusAttrList  = (sa{sv}av)
//   IBusAttribute = (sa{sv}uuuu) : type, value, start, end
//   IBusProperty  = (sa{sv}suvsvbbuvv) : key, type, label, icon, tooltip,
//                   sensitive, visible, state, sub_props, symbol
//   IBusPropList  = (sa{sv}av)

use std::collections::HashMap;
use zvariant::{Array, Signature, Structure, StructureBuilder, Value};

pub const ATTR_TYPE_UNDERLINE: u32 = 1;
pub const ATTR_UNDERLINE_SINGLE: u32 = 1;

pub const PROP_TYPE_NORMAL: u32 = 0;
pub const PROP_TYPE_TOGGLE: u32 = 1;
pub const PROP_TYPE_RADIO: u32 = 2;
pub const PROP_TYPE_MENU: u32 = 3;

pub const PROP_STATE_UNCHECKED: u32 = 0;
pub const PROP_STATE_CHECKED: u32 = 1;

pub const PREEDIT_FOCUS_MODE_COMMIT: u32 = 1;

fn attachments() -> HashMap<String, Value<'static>> {
    HashMap::new()
}

fn variant_array(items: Vec<Structure<'static>>) -> Array<'static> {
    let mut arr = Array::new(&Signature::Variant);
    for it in items {
        arr.append(Value::new(Value::Structure(it))).expect("append variant");
    }
    arr
}

fn attribute(attr_type: u32, value: u32, start: u32, end: u32) -> Structure<'static> {
    StructureBuilder::new()
        .add_field("IBusAttribute".to_string())
        .add_field(attachments())
        .add_field(attr_type)
        .add_field(value)
        .add_field(start)
        .add_field(end)
        .build()
        .unwrap()
}

fn attr_list(attrs: Vec<Structure<'static>>) -> Structure<'static> {
    StructureBuilder::new()
        .add_field("IBusAttrList".to_string())
        .add_field(attachments())
        .add_field(variant_array(attrs))
        .build()
        .unwrap()
}

/// IBusText (chưa bọc variant - zvariant tự bọc khi dùng làm 'v').
pub fn text(s: &str, underline: bool) -> Structure<'static> {
    let n = s.chars().count() as u32;
    let attrs = if underline && n > 0 {
        vec![attribute(ATTR_TYPE_UNDERLINE, ATTR_UNDERLINE_SINGLE, 0, n)]
    } else {
        vec![]
    };
    StructureBuilder::new()
        .add_field("IBusText".to_string())
        .add_field(attachments())
        .add_field(s.to_string())
        .append_field(Value::new(Value::Structure(attr_list(attrs))))
        .build()
        .unwrap()
}

pub struct PropSpec {
    pub key: String,
    pub prop_type: u32,
    pub label: String,
    pub icon: String,
    pub tooltip: String,
    pub sensitive: bool,
    pub state: u32,
    pub symbol: String,
    pub sub_props: Vec<PropSpec>,
}

impl PropSpec {
    pub fn new(key: &str, prop_type: u32, label: &str) -> PropSpec {
        PropSpec {
            key: key.to_string(),
            prop_type,
            label: label.to_string(),
            icon: String::new(),
            tooltip: String::new(),
            sensitive: true,
            state: PROP_STATE_UNCHECKED,
            symbol: String::new(),
            sub_props: Vec::new(),
        }
    }

    pub fn tooltip(mut self, t: &str) -> Self {
        self.tooltip = t.to_string();
        self
    }
}

/// IBusProperty (chưa bọc variant).
pub fn property(p: &PropSpec) -> Structure<'static> {
    let subs: Vec<Structure> = p.sub_props.iter().map(property).collect();
    StructureBuilder::new()
        .add_field("IBusProperty".to_string())
        .add_field(attachments())
        .add_field(p.key.clone())
        .add_field(p.prop_type)
        .append_field(Value::new(Value::Structure(text(&p.label, false))))
        .add_field(p.icon.clone())
        .append_field(Value::new(Value::Structure(text(&p.tooltip, false))))
        .add_field(p.sensitive)
        .add_field(true) // visible
        .add_field(p.state)
        .append_field(Value::new(Value::Structure(prop_list(subs))))
        .append_field(Value::new(Value::Structure(text(&p.symbol, false))))
        .build()
        .unwrap()
}

/// IBusPropList (chưa bọc variant).
pub fn prop_list(props: Vec<Structure<'static>>) -> Structure<'static> {
    StructureBuilder::new()
        .add_field("IBusPropList".to_string())
        .add_field(attachments())
        .add_field(variant_array(props))
        .build()
        .unwrap()
}
