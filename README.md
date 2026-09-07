# ViKey (Rust) – bộ gõ tiếng Việt Telex/VNI cho Linux (IBus)

Bản viết lại bằng **Rust** của ViKey: engine là MỘT binary native (~3 MB, chỉ phụ
thuộc glibc), nói chuyện thẳng với `ibus-daemon` qua D-Bus (thư viện zbus), không
cần Python hay GObject lúc gõ. Khởi động tức thì, nhẹ RAM, hành vi gõ **giống hệt
bản Python** – được chứng minh bằng bộ so khớp 15.456 trường hợp sinh từ engine
Python gốc và cùng một bộ kiểm thử đầu-cuối chạy qua `ibus-daemon` thật.

Tính năng đầy đủ như bản Python 1.4.0: Telex / VNI / cả hai; không duplicate text
(preedit + commit một lần, không Backspace giả); dùng được trong terminal; kiểm
tra chính tả – khôi phục phím với từ sai (`windows`, `status`, `sudo apt`… giữ
nguyên); đặt dấu kiểu cũ/mới; **bỏ dấu tự do** (gõ `dend` ra `đen`, `tienges` ra
`tiếng` – tuỳ chọn, mặc định tắt); gõ tắt kiểu Unikey (bảng `macros.txt`, tự chỉnh chữ
hoa, tuỳ chọn chạy cả khi tắt tiếng Việt); phím chuyển Việt/Anh Ctrl+Shift /
Alt+Z / tuỳ chỉnh (vd Ctrl+Shift+Space) / tắt; chế độ "Không gạch chân"; bảng mã
NFC/NFD; menu Vi/En trên thanh trên; trạng thái Việt/Anh chung mọi cửa sổ.

Cửa sổ **Cài đặt** (GTK4) vẫn là ứng dụng Python nhỏ đi kèm (chỉ là trình sửa
`config.json`/`macros.txt`); engine không cần nó để chạy. Hai bản Python/Rust
dùng chung file cấu hình `~/.config/ibus-vikey/` nên cài đè lẫn nhau thoải mái.

## Cài đặt (Ubuntu 22.04 / 24.04 / 26.04)

```bash
unzip ibus-vikey-full.zip
cd ibus-vikey-rust
./setup.sh            # KHÔNG dùng sudo; script tự hỏi mật khẩu khi cần
```

`setup.sh` làm trọn gói trong một lệnh: cài phụ thuộc, engine, lệnh `vikey`,
icon hệ thống + shortcut **ViKey** trong Activities, xoá cache cũ (registry IBus,
bản cài cũ) để engine hiện ra ngay, đặt IBus làm khung nhập liệu và thêm vào
Input Sources. (`install.sh` là tên gọi khác của cùng script.)

Gói kèm **binary dựng sẵn** cho x86_64 (build trên Ubuntu 24.04, chạy được trên
24.04/26.04). Nếu binary không chạy trên máy bạn (vd ARM), script tự biên dịch
từ mã nguồn: cần `cargo` (`sudo apt install cargo` hoặc rustup).

Sau khi cài: đăng xuất/đăng nhập nếu chưa thấy "Tiếng Việt (ViKey)" trong
*Settings → Keyboard → Input Sources*; chuyển bộ gõ bằng Super+Space.

Bản này cài đè lên bản Python (cùng tên engine `vikey`, cùng chỗ
`/usr/share/ibus-vikey`) – nguồn nhập đã thêm sẵn vẫn dùng được luôn.

## Gỡ cài đặt

```bash
./uninstall.sh                 # gỡ SẠCH: engine, shortcut, icon, cache, và cả
                               # cấu hình + bảng gõ tắt (~/.config/ibus-vikey)
./uninstall.sh --keep-config   # gỡ nhưng GIỮ cấu hình/bảng gõ tắt để cài lại sau
```

## Dòng lệnh

```bash
vikey --test "tieesng vieejt"        # gõ thử, không cần IBus
vikey --config                       # xem cấu hình; vikey --config method vni ...
vikey --macro                        # bảng gõ tắt; add/del/edit/init
vikey --setup                        # cửa sổ Cài đặt (GTK4)
```

Khoá cấu hình (`~/.config/ibus-vikey/config.json`): `method` (telex|vni|both),
`toggle_key` (ctrl_shift|alt_z|custom|none), `toggle_custom`
(`"<Control><Shift>space"`…), `charset` (precomposed|decomposed), `enabled`,
`spell_check`, `modern_tone`, `free_marking`, `macros`, `macros_when_off`,
`direct_mode`, `direct_key` (accelerator, rỗng = tắt).
Đổi cấu hình có hiệu lực khi focus vào ô nhập tiếp theo, không cần khởi động lại.

## Ô nhập contenteditable có tô màu cú pháp (Adminer…)

Vài trang web dùng `<pre contenteditable="true">` kèm script tô màu chạy trên
mỗi sự kiện `input` (Adminer + JUSH là ví dụ). Script ghi đè `innerHTML` nên phá
mất composition range mà trình duyệt đang giữ cho preedit; các mẩu preedit dồn
lại thành chữ thừa – gõ `mate` ra `mmatmatemate`. Lỗi này xảy ra với mọi bộ gõ,
không riêng ViKey.

Cách chữa: bật **Không gạch chân** (`direct_mode`) – engine bỏ preedit, gửi chữ
thẳng vào ứng dụng nên không còn composition range cho script phá. Vì chế độ này
lại dễ lặp chữ trong terminal, có phím tắt để bật/tắt nhanh khi chuyển app:

```bash
vikey --config direct_key "<Control><Shift>d"   # đặt phím tắt
vikey --config direct_key ""                    # bỏ phím tắt
```

Trong cửa sổ Cài đặt: thẻ *Tuỳ chọn* → *Nâng cao* → nút cạnh công tắc "Không
gạch chân" (Backspace trong hộp thoại để bỏ phím tắt).

Ngoài ra engine đọc cờ `IBUS_CAP_PREEDIT_TEXT`: client nào không khai báo hỗ trợ
preedit thì tự dùng lối gõ trực tiếp, không ghi đè tuỳ chọn trong `config.json`.
(Chrome *có* khai báo hỗ trợ preedit nên trường hợp Adminer vẫn phải bật tay.)

## Phím mũi tên khi đang gõ dở

Đang có từ chưa chốt (preedit) mà bấm mũi tên / Home / End / PageUp / PageDown /
Delete: engine chốt từ và **nuốt phím đó**; bấm lần nữa mới di chuyển con trỏ.

Cần vậy vì nếu vừa commit chữ vừa thả phím xuống ứng dụng trong cùng một nhịp,
`zsh-autosuggestions` (fetch gợi ý bất đồng bộ) chưa kịp cập nhật và mũi tên phải
sẽ dán lại gợi ý cũ – gõ `pnpm d` rồi bấm `→` ra `pnpm ddb:migrate && pnpm
db:generate`. Enter/Tab không đổi (vẫn xuống ứng dụng), F1..F12 cũng vậy.

## Bỏ dấu tự do (`free_marking`)

Mặc định **tắt** – gõ theo lối Telex/VNI cổ điển: phím dấu phải đứng ngay sau chữ
cái gốc (`ddeen`, `tieeng`). Bật lên thì phím dấu tìm mục tiêu trong cả âm tiết,
nên đặt được ở cuối từ:

```bash
vikey --config free_marking on
vikey --test "dend duongwd tienges khongo dauad"   # đen đương tiếng không đâu
```

| Nhóm phím | Tắt | Bật |
|---|---|---|
| `dd` / `9` (đ) | phải liền: `dden` | tự do: `dend`, `duongwd` |
| `aa ee oo` / `6` (â ê ô) | phải liền: `tieeng` | tự do: `tienge`, `khongo` |
| `w` / `7` `8` (ơ ư ă) | tự do sẵn | tự do |
| `s f r x j` / `1`-`5` (thanh) | tự do sẵn | tự do |

Gõ lặp phím dấu để hoàn tác (`bietee` → `biete`) chỉ nhận khi phím nằm ngay sau
phím đã tạo dấu – hoàn tác từ xa sẽ nuốt mất một chữ đã gõ (`banana`).

Đánh đổi: vài từ tiếng Anh có dạng âm tiết hợp lệ tiếng Việt sẽ bị biến đổi
(`dad` → `đa`, `data` → `dât`, `deed` → `đê`). Kiểm tra chính tả vẫn giữ nguyên
`windows`, `sudo`, `status`, `added`, `dodge`, `google`… Bấm phím chuyển Việt/Anh
khi cần gõ tiếng Anh nhiều.

## Mã nguồn & kiểm thử

```
src/vnengine.rs        bộ gõ Telex/VNI (port 1:1 từ vnengine.py)
src/keyhandler.rs      xử lý phím / preedit / commit / gõ tắt / phím chuyển
src/hotkey.rs          phân tích tổ hợp phím "<Control><Shift>space"
src/config.rs          config.json (tương thích bản Python)
src/macros_table.rs    macros.txt (tương thích bản Python)
src/ibus_serde.rs      wire-format IBusText/IBusProperty... (zvariant)
src/engine_service.rs  đối tượng D-Bus org.freedesktop.IBus.Engine
src/ibus_main.rs       kết nối ibus-daemon, Factory, vòng đời
tests/engine_equiv.rs  so khớp 15.456 trường hợp + 300 chuỗi Backspace với bản Python
tests/keyhandler_test.rs  25 kịch bản chống duplicate/gõ tắt/phím chuyển/mũi tên/direct
tests/free_marking.rs  7 kịch bản bỏ dấu tự do (bật/tắt, hoàn tác, backspace)
tests/e2e_ibus.py      kiểm thử đầu-cuối qua ibus-daemon thật (dùng chung với bản Python)
```

```bash
cargo test                           # unit + so khớp với engine Python
python3 tests/e2e_ibus.py            # cần ibus-daemon đang chạy + đã cài ViKey
```

## Vì sao không duplicate text?

Giống bản Python: từ đang gõ chỉ nằm trong preedit; kết thúc từ commit đúng một
lần (ký tự kết thúc đi cùng gói commit); khi mất focus/click chuột, IBus/GNOME
Shell tự commit phần dở (preedit mode COMMIT) và engine không commit lần hai;
không `forward_key_event`, không Backspace giả; `delete_surrounding_text` chỉ
dùng khi bạn tự bật "Không gạch chân"/"Gõ tắt khi tắt tiếng Việt".

## Tóm tắt dự án

### Đã làm

* **Bộ gõ Telex hoàn chỉnh** (rồi thêm VNI và chế độ Telex + VNI cùng lúc): dấu
  thanh tự do (`toans` → toán), `uo`+`w` → ươ, xử lý huơ/thuở/hương, gõ lặp phím
  dấu để lấy chữ gốc (`ass` → as, `tesst` → test), bảo toàn chữ hoa.
* **Chống duplicate text tận gốc**: chỉ dùng preedit + commit một lần, không
  Backspace giả, không forward_key_event; preedit mode COMMIT để đổi cửa sổ /
  click chuột không mất chữ và không lặp chữ. **Dùng tốt trong terminal** (Enter,
  Esc, Tab, Ctrl+... luôn được nhường lại cho ứng dụng).
* **Kiểm tra chính tả – khôi phục phím với từ sai**: `windows`, `status`, `data`,
  `sudo apt install`… giữ nguyên phím gõ.
* **Gõ tắt kiểu Unikey**: bảng `macros.txt`, tự chỉnh chữ hoa (vn/Vn/VN), không
  bung giữa `file.vn`; sửa bằng GUI/CLI/file, hiệu lực ngay; tuỳ chọn gõ tắt cả
  khi tắt tiếng Việt.
* **Đủ setting cơ bản kiểu Unikey**: kiểu gõ, phím chuyển Việt/Anh (Ctrl+Shift /
  Alt+Z / tổ hợp tuỳ chỉnh vd Ctrl+Shift+Space / tắt), bảng mã NFC/NFD, đặt dấu
  kiểu cũ/mới, bật khi khởi động; trạng thái Việt/Anh chung mọi cửa sổ.
* **Cửa sổ Cài đặt GTK4** (3 thẻ: Tuỳ chọn / Gõ tắt / Thông tin, có nút bắt tổ
  hợp phím), menu Vi/En trên thanh trên, shortcut ViKey trong Activities, lệnh
  `vikey` đầy đủ (--test/--config/--macro/--setup).
* **Viết lại engine bằng Rust** (v2.0): một binary native ~3 MB nói chuyện thẳng
  với ibus-daemon qua D-Bus (zbus), không cần Python/GObject lúc gõ; tự cài đặt
  wire-format IBusText/IBusProperty.
* **Kiểm thử kỹ**: 36 unit test Python; 16 test Rust trong đó bộ so khớp
  **15.456 trường hợp + 300 chuỗi Backspace** sinh từ engine Python để bảo đảm
  hành vi giống hệt; bộ kiểm thử đầu-cuối **31 kịch bản chạy qua ibus-daemon
  thật** (focus out, reset, Ctrl+C, gõ tắt, VNI, phím chuyển, không gạch chân…).
* **setup.sh / uninstall.sh trọn gói**: cài một lệnh (kèm icon hệ thống, shortcut,
  xoá cache registry IBus), gỡ một lệnh sạch tuyệt đối kể cả cấu hình
  (`--keep-config` nếu muốn giữ).

### Còn cần làm / hướng phát triển

* **Chưa kiểm thử trên máy thật** với GNOME Shell Wayland (mọi kiểm thử chạy qua
  ibus-daemon thật nhưng trong môi trường ảo X11). Cần anh dùng thử vài ngày,
  đặc biệt: Chrome/VS Code (Wayland cần cờ `--enable-wayland-ime`), LibreOffice,
  app Qt/KDE.
* Binary dựng sẵn mới có **x86_64**; máy ARM phải tự `cargo build` (script tự
  làm). Có thể build sẵn thêm aarch64.
* Đóng gói chuẩn **.deb / PPA / Flatpak** để cài bằng `apt install` và tự cập
  nhật, thay cho tarball + script.
* Viết lại **cửa sổ Cài đặt bằng Rust (GTK4-rs)** để bỏ hẳn phụ thuộc Python.
* Gõ tắt nâng cao: nội dung nhiều dòng, đếm số lần dùng, import bảng gõ tắt
  từ Unikey Windows.
* Tự nhớ **bật/tắt tiếng Việt theo từng ứng dụng** (khó trên Wayland vì engine
  không biết tên app; cần khảo sát thêm).
* Bảng mã cũ TCVN3 / VNI-Windows: chưa hỗ trợ (chủ đích, vì đã lỗi thời) — chỉ
  thêm nếu thực sự cần.
* Trang GitHub công khai + CI chạy bộ kiểm thử tự động.

## Hướng dẫn sử dụng nhanh

1. **Cài**: giải nén → `./setup.sh` → đăng xuất/đăng nhập.
2. **Chọn bộ gõ**: bấm Super+Space tới khi thấy **Vi** trên thanh trên (hoặc bấm
   biểu tượng bàn phím → Tiếng Việt (ViKey)).
3. **Gõ Telex**: `aa ee oo` → â ê ô; `aw ow uw` → ă ơ ư; `dd` → đ;
   `s f r x j` → sắc huyền hỏi ngã nặng; `z` xoá dấu.
   Ví dụ: `Tieesng Vieejt` → Tiếng Việt, `nguowif` → người, `dduwowngf` → đường.
4. **Đang gõ lệnh/tiếng Anh?** Bấm **Ctrl+Shift** (hoặc tổ hợp anh đã chọn) để
   tạm chuyển **En**, bấm lại để về **Vi**.
5. **Gõ tắt**: gõ `vn` rồi space → "Việt Nam". Thêm mục mới: mở Cài đặt → thẻ
   Gõ tắt, hoặc `vikey --macro add tphcm "Thành phố Hồ Chí Minh"`.
6. **Chỉnh tuỳ chọn**: gõ "ViKey" trong Activities, hoặc menu Vi/En → *Cài đặt
   ViKey…*, hoặc `vikey --config`.
7. **Trục trặc?** `ibus restart`; chưa thấy engine thì đăng xuất/đăng nhập;
   gõ thử không cần IBus: `vikey --test "xin chaof"`.
