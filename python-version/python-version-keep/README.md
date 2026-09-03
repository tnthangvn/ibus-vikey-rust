# ViKey – bộ gõ tiếng Việt (Telex / VNI) cho Linux (IBus)

Bộ gõ kiểu Unikey, viết bằng Python, chạy trên IBus (khung nhập liệu mặc định của
Ubuntu). Mục tiêu chính: **không bao giờ bị lặp/duplicate chữ** và **gõ được
trong terminal** (GNOME Terminal, Console, Tilix, Kitty, Alacritty, vim, tmux...).

## Vì sao không bị duplicate text?

Các bộ gõ hay bị lặp chữ vì chúng "sửa" chữ đã gửi vào ứng dụng bằng cách gửi
Backspace giả rồi gửi lại chữ mới. Trong terminal, Chrome/Electron, hoặc khi ứng
dụng xử lý phím chậm, các Backspace giả này đến sai thứ tự và chữ bị nhân đôi.

ViKey không làm vậy:

* Từ đang gõ chỉ nằm trong **preedit** (đoạn gạch chân). Ứng dụng chưa nhận gì.
* Khi kết thúc từ (space, dấu câu, Enter...), ViKey **commit đúng một lần** rồi
  xoá preedit. Ký tự kết thúc từ được commit chung với từ trong cùng một gói
  nên không thể "tới trước" từ.
* Khi bạn click chuột chỗ khác hoặc đổi cửa sổ, IBus/GNOME Shell tự commit phần
  đang gõ (chế độ preedit `COMMIT`), ViKey **không commit lần thứ hai**.
* Không dùng `forward_key_event`, không dùng `delete_surrounding_text` (trừ khi bạn tự bật chế độ "Không gạch chân" bên dưới).

Có bộ kiểm thử đầu-cuối chạy qua `ibus-daemon` thật (`tests/e2e_ibus.py`) để
chứng minh điều đó: focus out, reset, Esc, Ctrl+C, Backspace... đều cho ra đúng
một bản chữ.

## Tính năng

* **Kiểu gõ Telex, VNI hoặc cả hai cùng lúc.** Telex: `aa ee oo aw ow uw dd`,
  dấu `s f r x j`, `z` xoá dấu, `w` = ư. VNI: `6 7 8 9` → â/ê/ô, ơ/ư, ă, đ; `1-5`
  dấu thanh; `0` xoá dấu.
* Gõ dấu tự do: `toans` → toán, `hoangf` → hoàng, `duongw` → dương.
* `uo` + `w` → ươ (`nguowif` → người), `huow` → huơ / `huowng` → hương, `thuowr` → thuở.
* Gõ lặp phím dấu để lấy chữ gốc: `ass` → as, `tesst` → test, `ddd` → dd, `ww` → w.
* **Kiểm tra chính tả + khôi phục phím**: từ không phải tiếng Việt giữ nguyên
  phím bạn gõ – `windows`, `status`, `data`, `tools`, `book`, `banana`,
  `sudo apt install`... không bị biến dạng. Rất hợp khi gõ lệnh trong terminal.
* Đặt dấu kiểu cũ (hòa, khỏe, thúy) hoặc kiểu mới (hoà, khoẻ, thuý) – tuỳ chọn.
* **Phím chuyển Việt/Anh**: Ctrl+Shift (bấm rồi thả, không kèm phím khác, giống
  Unikey), Alt+Z, **tuỳ chỉnh bất kỳ tổ hợp nào** (vd Ctrl+Shift+Space, Alt+`,
  Shift+F12 – bấm nút trong Cài đặt rồi gõ tổ hợp), hoặc tắt. Trạng thái Việt/Anh
  dùng chung cho mọi cửa sổ.
* Bảng mã Unicode dựng sẵn (mặc định) hoặc Unicode tổ hợp.
* Menu trên thanh trên cùng (biểu tượng Vi/En) để bật/tắt và đổi tuỳ chọn, và
  **cửa sổ Cài đặt** (GTK4) với bảng gõ tắt sửa trực tiếp.
* Tuỳ chọn **"Không gạch chân"** (gõ trực tiếp, không preedit) cho ứng dụng soạn
  thảo – xem mục riêng bên dưới.
* **Gõ tắt** kiểu Unikey: `vn` → Việt Nam, `tphcm` → Thành phố Hồ Chí Minh…,
  bảng do bạn tự soạn, tự điều chỉnh chữ hoa (`Vn` → Việt Nam, `VN` → VIỆT NAM);
  tuỳ chọn gõ tắt cả khi đang tắt tiếng Việt.
* Bảo toàn chữ hoa: `TIEENGS` → TIẾNG, `Ddaij` → Đại.

## Cài đặt (Ubuntu 22.04 / 24.04 / 26.04, GNOME)

```bash
tar xzf ibus-vikey.tar.gz
cd ibus-vikey
./install.sh          # KHÔNG dùng sudo; script tự hỏi mật khẩu khi cần
```

Script sẽ: cài `ibus python3-gi gir1.2-ibus-1.0 gir1.2-gtk-4.0`, chép bộ gõ vào
`/usr/share/ibus-vikey`, đăng ký component với IBus, khởi động lại IBus và thêm
**Tiếng Việt (ViKey)** vào *Settings → Keyboard → Input Sources*.

Nếu chưa thấy trong danh sách nguồn nhập: **đăng xuất rồi đăng nhập lại** (GNOME
chỉ đọc danh sách engine khi khởi động phiên).

Chuyển sang ViKey bằng **Super+Space** hoặc bấm biểu tượng bàn phím trên thanh trên.

### Kubuntu / KDE Plasma

`./install.sh` vẫn cài được. Sau đó: *System Settings → Keyboard → Virtual
Keyboard → chọn "IBus Wayland"* (Plasma Wayland) hoặc để `im-config -n ibus` lo
(X11), rồi chạy `ibus-setup` → Input Method → Add → Vietnamese → Tiếng Việt (ViKey).

### Gỡ cài đặt

```bash
./uninstall.sh
```

## Dùng trong terminal

Không cần cấu hình gì thêm: GNOME Terminal/Console/Tilix/Kitty/Alacritty/WezTerm
đều hỗ trợ preedit của IBus. Từ đang gõ hiện gạch chân, bấm space/Enter là được
commit vào shell. Phím Enter/Tab/Esc/Ctrl+... luôn được nhường lại cho terminal
sau khi commit từ đang dở, nên vim, tmux, fzf, less... hoạt động bình thường.

Mẹo: khi gõ lệnh dài toàn tiếng Anh, bấm phím chuyển (**Ctrl+Shift** hoặc
**Alt+Z**, tuỳ cài đặt) để tắt tiếng Việt tạm thời (biểu tượng đổi thành **En**),
bấm lại để bật.

Gõ thử ngay không cần IBus:

```bash
vikey --test "tieesng vieejt raats hay"
# -> tiếng việt rất hay
```

## Chế độ "Không gạch chân" (gõ trực tiếp)

Mặc định từ đang gõ hiện gạch chân (preedit). Đó là cơ chế an toàn tuyệt đối:
ứng dụng chỉ nhận chữ đúng một lần khi từ đã hoàn chỉnh. Trên Wayland, gạch chân
do ứng dụng vẽ (GTK4, VTE, GNOME Shell) nên bộ gõ không thể "giữ preedit mà bỏ
gạch chân"; muốn không gạch chân thì phải gõ thẳng vào ứng dụng và sửa lại chữ
khi cần (`s` → dấu sắc).

ViKey có chế độ này, **mặc định tắt**. Bật bằng menu Vi/En trên thanh trên →
*Không gạch chân (gõ trực tiếp)*, hoặc:

```bash
vikey --config direct_mode on
```

Cơ chế: chữ được commit ngay từng phím; khi từ đổi dạng, ViKey xoá phần khác biệt
bằng `delete_surrounding_text` (một lệnh nguyên tử, không bắn Backspace giả) rồi
commit phần mới. Hoạt động tốt trong LibreOffice, Firefox, GNOME Text Editor,
các app GTK/Qt. **Không nên dùng trong terminal** (vim, tmux, bash) và một số
app không hỗ trợ surrounding text (một số Electron/Chrome): lệnh xoá bị bỏ qua
nên chữ sẽ bị lặp. Khi gặp lặp chữ ở đâu, cứ tắt chế độ này là hết ngay – việc
bật/tắt là một cú click trên menu, áp dụng tức thì.

## Gõ tắt

Bảng gõ tắt nằm ở `~/.config/ibus-vikey/macros.txt` (install.sh tạo sẵn file
mẫu), mỗi dòng một mục:

```
# viết_tắt:nội_dung_đầy_đủ
vn:Việt Nam
tphcm:Thành phố Hồ Chí Minh
email:ten.cua.ban@gmail.com
```

Viết tắt chỉ gồm chữ cái a–z (không phân biệt hoa/thường); nội dung tuỳ ý, có
dấu cách, dấu câu, có cả dấu `:` cũng được. Gõ viết tắt rồi bấm **space, dấu câu,
Enter hoặc Tab** là bung ra nội dung đầy đủ. Chữ hoa tự điều chỉnh theo cách gõ:
`vn` → Việt Nam, `Vn` → Việt Nam (hoa chữ đầu), `VN` → VIỆT NAM.

Không bung khi viết tắt dính liền ký tự khác phía trước (`file.vn`, `a-vn`,
`user@vn`) nên tên file, đường dẫn, địa chỉ mail trong terminal không bị đụng;
cũng không bung khi bấm Esc, phím mũi tên hay Ctrl+…

Sửa bảng bằng cách nào cũng được, lưu xong là có hiệu lực ngay (không cần khởi
động lại IBus):

```bash
vikey --macro                        # xem bảng
vikey --macro add vn "Việt Nam"      # thêm hoặc sửa
vikey --macro del vn                 # xoá
vikey --macro edit                   # mở file bằng trình soạn thảo
```

Hoặc dùng thẻ **Gõ tắt** trong cửa sổ Cài đặt (menu Vi/En → *Cài đặt ViKey…*).
Tắt/bật nhanh toàn bộ gõ tắt: menu → *Gõ tắt*, hay `vikey --config macros off`.

Gõ tắt hoạt động ở cả hai chế độ (có/không gạch chân). Mặc định chỉ chạy khi
tiếng Việt đang bật (biểu tượng **Vi**); bật *Gõ tắt cả khi tắt tiếng Việt* nếu
muốn dùng cả ở chế độ En (cơ chế xoá-thay chữ như "Không gạch chân", cùng lưu ý
về terminal).

## Cửa sổ Cài đặt

Mở bằng một trong các cách: menu Vi/En trên thanh trên → **Cài đặt ViKey…**;
gõ "ViKey" trong Activities; hoặc lệnh `vikey --setup`. Cửa sổ có ba thẻ:

* **Tuỳ chọn** – *Cơ bản*: kiểu gõ (Telex / VNI / Telex + VNI), phím chuyển
  Việt/Anh (Ctrl+Shift / Alt+Z / Tuỳ chỉnh – bấm nút rồi gõ tổ hợp / không), bảng mã, bật tiếng Việt khi khởi động,
  kiểm tra chính tả, kiểu đặt dấu. *Gõ tắt*: cho phép gõ tắt, gõ tắt cả khi tắt
  tiếng Việt. *Nâng cao*: không gạch chân. Gạt/chọn là lưu ngay.
* **Gõ tắt** – bảng viết tắt / nội dung sửa trực tiếp, nút Thêm / xoá từng dòng /
  Lưu / Nạp lại / Mở file. Đóng cửa sổ cũng tự lưu nếu bảng hợp lệ.
* **Thông tin** – phiên bản, phím tắt, đường dẫn file cấu hình.

Không cần khởi động lại IBus sau khi đổi: bộ gõ tự nạp lại khi bạn bấm vào ô nhập
tiếp theo.

## Cấu hình bằng file / dòng lệnh

File `~/.config/ibus-vikey/config.json` (tự tạo lần đầu):

| Khoá                | Mặc định       | Ý nghĩa                                                        |
|---------------------|----------------|----------------------------------------------------------------|
| `method`            | `telex`        | Kiểu gõ: `telex` \| `vni` \| `both` (Telex + VNI)               |
| `toggle_key`        | `ctrl_shift`   | Phím chuyển Việt/Anh: `ctrl_shift` \| `alt_z` \| `custom` \| `none` |
| `toggle_custom`     | `<Control><Shift>space` | Tổ hợp khi `toggle_key = custom`, dạng accelerator GTK (`<Alt>grave`, `<Shift>F12`, `<Super>z`…) |
| `charset`           | `precomposed`  | Bảng mã: `precomposed` (Unicode dựng sẵn) \| `decomposed` (tổ hợp) |
| `enabled`           | `true`         | Trạng thái tiếng Việt khi khởi động                            |
| `spell_check`       | `true`         | Khôi phục phím thô với từ không phải tiếng Việt                |
| `modern_tone`       | `false`        | `true`: hoà/khoẻ/thuý – `false`: hòa/khỏe/thúy                 |
| `macros`            | `true`         | Bật gõ tắt (bảng `macros.txt`)                                 |
| `macros_when_off`   | `false`        | Gõ tắt cả khi đang tắt tiếng Việt (cơ chế xoá-thay như không gạch chân) |
| `direct_mode`       | `false`        | Không gạch chân / gõ trực tiếp (không dùng trong terminal)     |

Đổi nhanh bằng dòng lệnh (áp dụng khi focus vào ô nhập tiếp theo):

```bash
vikey --config                    # xem
vikey --config method vni
vikey --config toggle_key custom
vikey --config toggle_custom "<Control><Shift>space"
vikey --config modern_tone on
vikey --config spell_check off
```

Hoặc bấm vào biểu tượng Vi/En trên thanh trên cùng → menu tuỳ chọn.

## Cấu trúc mã nguồn

```
vikey/vnengine.py    bộ gõ Telex thuần Python (không phụ thuộc IBus) – logic dấu, đặt dấu, chính tả
vikey/keyhandler.py  xử lý phím / preedit / commit, độc lập IBus để unit-test được
vikey/engine.py      lớp IBus (IBus.Engine, IBus.Factory, menu)
vikey/main.py        điểm vào: --ibus | --standalone | --setup | --config | --macro | --test
vikey/settings.py    cửa sổ Cài đặt (GTK4)
vikey/config.py      đọc/ghi ~/.config/ibus-vikey/config.json
vikey/hotkey.py      phân tích tổ hợp phím chuyển tuỳ chỉnh ("<Control><Shift>space")
vikey/macros.py      bảng gõ tắt ~/.config/ibus-vikey/macros.txt
vikey.xml.in         component IBus (install.sh điền đường dẫn)
tests/               unit test + kiểm thử đầu-cuối qua ibus-daemon thật
```

Chạy test:

```bash
python3 -m unittest discover -s tests        # unit test, không cần IBus
python3 tests/e2e_ibus.py                     # cần ibus-daemon đang chạy + đã cài ViKey
```

## Xử lý sự cố

* **Không thấy "Tiếng Việt (ViKey)"**: `ibus list-engine | grep -i vikey`. Nếu có
  mà GNOME không hiện → đăng xuất/đăng nhập; hoặc
  `gsettings set org.gnome.desktop.input-sources show-all-sources true`.
* **Không gõ được gì**: `ibus restart`; xem log `journalctl --user -b | grep -i vikey`
  hoặc chạy tay `/usr/share/ibus-vikey/main.py --standalone` để thấy lỗi.
* **Gõ tiếng Anh bị bỏ dấu** (`this` → thí): đó là bản chất Telex (Unikey cũng
  vậy). Bấm Ctrl+Shift để tắt tạm, hoặc gõ lặp phím dấu (`thiss` → this).
* **Ứng dụng Snap/Flatpak** (một số bản Chrome, VS Code): vẫn dùng IBus qua
  portal; nếu không thấy gạch chân, kiểm tra biến `GTK_IM_MODULE=ibus`
  (`im-config -n ibus` rồi đăng nhập lại).
