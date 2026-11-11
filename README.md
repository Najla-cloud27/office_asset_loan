# Office Asset Loan

Modul Odoo 19 Community Edition untuk mencatat inventaris aset kantor beserta
riwayat peminjaman dan pengembaliannya.

| Informasi | Keterangan |
| --- | --- |
| Nama Modul | Office Asset Loan |
| Versi | 19.0.1.0.0 |
| Odoo | 19.0 Community Edition (CE) |
| Kategori | Tools |
| Author | **Najla Haura Mumtazah** |
| Lisensi | LGPL-3 |
| Dependensi | `base` |
| Aplikasi | Ya (`application: True`) |

---

## 1. Deskripsi Modul

**Office Asset Loan** adalah modul manajemen aset kantor yang dibuat untuk
memenuhi kebutuhan pencatatan inventaris sekaligus peminjaman aset oleh
karyawan. Modul ini menyediakan dua model utama:

- **Office Asset** (`office.asset`) — master data aset kantor seperti laptop,
  meja, kendaraan, dan lain-lain, lengkap dengan kategori, kondisi, dan status
  ketersediaan.
- **Office Asset Loan** (`office.asset.loan`) — transaksi peminjaman aset yang
  mencatat peminjam, tanggal pinjam, jatuh tempo, tanggal kembali, serta
  status transaksi.

Setiap transaksi peminjaman memiliki alur status yang jelas
(`Draft → Borrowed → Returned`, atau `Cancelled`), nomor referensi otomatis,
serta validasi agar satu aset tidak dapat dipinjam oleh dua transaksi aktif
secara bersamaan.

---

## 2. Fitur Utama

### Master Data Aset
- Pencatatan nama aset, kode aset, kategori, kondisi, tanggal pembelian, dan catatan.
- Kategori aset: **Electronics**, **Furniture**, **Vehicle**, **Other**.
- Kondisi aset: **Good**, **Fair**, **Damaged** (ditampilkan dengan badge berwarna).
- Status **Available** yang dihitung otomatis dari ada/tidaknya peminjaman berstatus *Borrowed*.
- Penghitung jumlah peminjaman (`loan_count`) per aset.
- Dukungan arsip aset melalui field `active` (toggle Aktif/Non-aktif).
- Tab **Loans** pada form aset untuk melihat riwayat peminjaman aset tersebut.

### Transaksi Peminjaman
- Nomor referensi otomatis dengan format `LOAN/0001` (sequence, padding 4 digit).
- Peminjam default adalah user yang sedang login, dapat diubah.
- Perhitungan otomatis **Duration (Days)** dari selisih tanggal pinjam dan jatuh tempo.
- Indikator **Overdue** otomatis untuk peminjaman yang melewati jatuh tempo
  (dapat difilter pada pencarian).
- Tombol aksi: **Borrow**, **Return**, dan **Cancel** dengan status bar.
- Peringatan visual (alert) pada form saat peminjaman terlambat.
- Daftar peminjaman menandai baris yang terlambat dan yang dibatalkan.

### Antarmuka & Menu
- Menu utama **Asset Loan → Management**, berisi:
  - **Office Assets**
  - **Asset Loans**
- Tampilan *list*, *form*, dan *search* untuk kedua model.
- Empty-state help pada masing-masing tampilan agar memudahkan pengguna baru.

### Keamanan
- Hak akses diberikan kepada grup `base.group_user` (Internal User):
  - **Office Asset**: baca, ubah, buat (hapus tidak diizinkan).
  - **Office Asset Loan**: baca, ubah, buat, hapus (hapus dibatasi oleh Business Rule BR-7).

---

## 3. Business Rules

Aturan bisnis berikut diterapkan di dalam modul dan diberi label BR-1 sampai BR-8
pada kode sumber.

### BR-1 — Kode Aset Harus Unik
Setiap aset wajib memiliki `code` yang unik. Duplikasi kode aset ditolak pada
level database melalui constraint `UNIQUE(code)`.

- **Implementasi:** `models.Constraint('UNIQUE(code)', ...)` pada `_constraints` di `models/office_asset.py`.
- **Pesan error:** *"Kode aset tidak boleh sama dengan aset lain!"*

### BR-2 — Jatuh Tempo Tidak Boleh Lebih Awal dari Tanggal Pinjam
`due_date` harus sama dengan atau lebih besar dari `loan_date`. Validasi
dilakukan di dua lapis: constraint Python (`@api.constrains`) dan constraint SQL
(`CHECK(due_date >= loan_date)`) agar tetap terjaga meskipun data diubah di luar ORM.

- **Implementasi:** `_check_dates()` dan `models.Constraint('CHECK(due_date >= loan_date)', ...)`.
- **Pesan error:** *"Tanggal Due Date tidak boleh lebih awal dari Tanggal Loan Date!"*

### BR-3 — Nomor Referensi Peminjaman Dibuat Otomatis
Saat transaksi peminjaman dibuat, field `name` yang masih bernilai `New` diisi
otomatis dari sequence `office.asset.loan` dengan format `LOAN/0001`.

- **Implementasi:** override `create()` dengan decorator `@api.model_create_multi`
  (standar Odoo 19) dan `ir.sequence.next_by_code()`.
- **Definisi sequence:** `data/office_asset_loan_sequence.xml` (prefix `LOAN/`, padding 4).

### BR-4 — Peminjaman Ditolak Jika Aset Rusak atau Sedang Dipinjam
Aksi **Borrow** hanya boleh dilakukan apabila:
1. Kondisi aset bukan **Damaged** (rusak), dan
2. Aset sedang **Available** (tidak ada peminjaman lain berstatus *Borrowed*).

Jika salah satu syarat tidak terpenuhi, sistem menampilkan error dan status
transaksi tidak berubah.

- **Implementasi:** `action_borrow()` dengan `UserError`.
- **Pesan error:** *"Peminjaman ditolak karena kondisi aset dalam keadaan Rusak (Damaged)!"*
  dan *"Aset ini sedang dipinjam oleh peminjaman lain!"*

### BR-5 — Pengembalian Aset Mencatat Tanggal Kembali
Aksi **Return** mengubah status transaksi menjadi **Returned** dan mengisi
`return_date` secara otomatis dengan tanggal hari ini (mengikuti zona waktu user).

- **Implementasi:** `action_return()` menggunakan `fields.Date.context_today(self)`.

### BR-6 — Pembatalan Peminjaman
Aksi **Cancel** mengubah status transaksi menjadi **Cancelled**. Tombol Cancel
hanya tersedia untuk transaksi berstatus **Draft** atau **Borrowed**; transaksi
yang sudah **Returned** atau **Cancelled** tidak dapat dibatalkan lagi.

- **Implementasi:** `action_cancel()` dengan validasi status dan `UserError`.

### BR-7 — Transaksi Borrowed/Returned Tidak Boleh Dihapus
Transaksi peminjaman yang sudah berstatus **Borrowed** atau **Returned** tidak
boleh dihapus untuk menjaga jejak audit. Penghapusan hanya diizinkan untuk
transaksi **Draft** dan **Cancelled**.

- **Implementasi:** `@api.ondelete(at_uninstall=False)` pada `_unlink_except_borrowed_or_returned()`
  dan pengaman tambahan pada override `unlink()`.
- **Pesan error:** *"Peminjaman yang berstatus Borrowed atau Returned tidak boleh dihapus!"*

### BR-8 — Jatuh Tempo Otomatis 7 Hari
Saat `loan_date` diisi atau diubah, `due_date` otomatis diisi dengan
`loan_date + 7 hari`. Pengguna tetap dapat mengubah `due_date` secara manual
selama tidak melanggar BR-2.

- **Implementasi:** `@api.onchange('loan_date')` pada `_onchange_loan_date()`
  menggunakan `timedelta(days=7)`.

---

## 4. Struktur Folder Modul

```text
office_asset_loan/
├── __init__.py                          # Entry point modul
├── __manifest__.py                      # Metadata modul (nama, versi, author, data)
├── README.md                            # Dokumentasi modul ini
├── data/
│   └── office_asset_loan_sequence.xml   # Sequence nomor referensi LOAN/0001
├── models/
│   ├── __init__.py                      # Import semua file model
│   ├── office_asset.py                  # Model office.asset (master aset)
│   └── office_asset_loan.py             # Model office.asset.loan (transaksi pinjam)
├── security/
│   └── ir.model.access.csv              # Hak akses model untuk base.group_user
└── views/
    ├── office_asset_views.xml           # List, form, search, action Office Asset
    ├── office_asset_loan_views.xml      # List, form, search, action, menu Asset Loan
    └── office_asset_menus.xml           # Struktur menu utama Asset Loan
```

### Penjelasan Singkat Setiap Folder

| Folder/File | Fungsi |
| --- | --- |
| `__manifest__.py` | Mendefinisikan metadata modul dan urutan pemuatan file data. |
| `models/` | Berisi definisi ORM (field, constraint, compute, aksi, business rules). |
| `views/` | Berisi definisi XML untuk tampilan list/form/search, window action, dan menu. |
| `security/` | Berisi aturan hak akses (`ir.model.access.csv`). |
| `data/` | Berisi data awal, yaitu sequence nomor referensi peminjaman. |

### Model dan Field Utama

**`office.asset` — Office Asset**

| Field | Tipe | Keterangan |
| --- | --- | --- |
| `name` | Char | Nama aset (wajib) |
| `code` | Char | Kode aset (wajib, unik — BR-1) |
| `category` | Selection | electronics / furniture / vehicle / other |
| `condition` | Selection | good / fair / damaged |
| `purchase_date` | Date | Tanggal pembelian |
| `note` | Text | Catatan internal |
| `active` | Boolean | Status arsip aset |
| `loan_ids` | One2many | Riwayat peminjaman aset |
| `loan_count` | Integer (compute) | Jumlah peminjaman |
| `is_available` | Boolean (compute) | Tersedia jika tidak ada loan berstatus *Borrowed* |

**`office.asset.loan` — Office Asset Loan**

| Field | Tipe | Keterangan |
| --- | --- | --- |
| `name` | Char | Nomor referensi `LOAN/0001` (BR-3) |
| `asset_id` | Many2one `office.asset` | Aset yang dipinjam (wajib) |
| `borrower_id` | Many2one `res.users` | Peminjam (default user login) |
| `loan_date` | Date | Tanggal pinjam |
| `due_date` | Date | Jatuh tempo (BR-2, BR-8) |
| `return_date` | Date | Tanggal kembali (BR-5) |
| `purpose` | Char | Keperluan peminjaman |
| `state` | Selection | draft / borrowed / returned / cancelled |
| `duration_days` | Integer (compute) | Durasi peminjaman dalam hari |
| `is_overdue` | Boolean (compute, searchable) | Penanda terlambat |

### Alur Status

```text
          action_borrow (BR-4)          action_return (BR-5)
  Draft ─────────────────────▶ Borrowed ─────────────────────▶ Returned
    │                              │
    │ action_cancel (BR-6)         │ action_cancel (BR-6)
    ▼                              ▼
 Cancelled                      Cancelled
```

---

## 5. Cara Instalasi

### Prasyarat
- Odoo 19.0 Community Edition sudah terpasang dan berjalan.
- Akses ke folder `addons` Odoo.
- Hak akses Administrator/Developer mode pada instance Odoo.

### Langkah Instalasi Manual

1. **Salin folder modul** `office_asset_loan` ke salah satu direktori `addons`
   yang terdaftar pada konfigurasi Odoo, misalnya:

   ```text
   C:\Program Files\Odoo 19.0.20260925\server\odoo\addons\office_asset_loan
   ```

   atau pada Linux:

   ```bash
   /opt/odoo/custom-addons/office_asset_loan
   ```

2. **Pastikan direktori addons terdaftar** pada file konfigurasi Odoo
   (`odoo.conf`):

   ```ini
   [options]
   addons_path = /opt/odoo/addons,/opt/odoo/custom-addons
   ```

3. **Restart service Odoo** agar modul terdeteksi:

   ```bash
   sudo systemctl restart odoo
   ```

   Pada Windows, restart service Odoo melalui *Services* atau jalankan ulang
   perintah Odoo.

4. **Aktifkan Developer Mode** (Settings → Activate the developer mode),
   lalu buka menu **Apps** dan klik **Update Apps List**.

5. **Cari modul** dengan kata kunci `Office Asset Loan`, lalu klik **Activate**
   / **Install**.

6. Setelah instalasi selesai, menu **Asset Loan** akan muncul pada navbar atas.

### Instalasi via Command Line

```bash
odoo-bin -c odoo.conf -d nama_database -i office_asset_loan --stop-after-init
```

Keterangan:
- `-d` — nama database tujuan.
- `-i` — install modul.
- `--stop-after-init` — hentikan server setelah proses instalasi selesai.

Untuk memperbarui modul setelah ada perubahan kode/view:

```bash
odoo-bin -c odoo.conf -d nama_database -u office_asset_loan --stop-after-init
```

### Verifikasi Instalasi

1. Buka menu **Asset Loan → Management → Office Assets**.
2. Buat satu aset baru (misalnya *Laptop Dell XPS* dengan kode `AST-001`).
3. Buka **Asset Loan → Management → Asset Loans**, buat peminjaman baru, dan
   pastikan nomor referensi otomatis terbentuk (`LOAN/0001`).
4. Klik **Borrow**, lalu **Return**, dan periksa perubahan status serta tanggal kembali.

---

## 6. Catatan Teknis (Odoo 19)

Modul ini mengikuti konvensi Odoo 19, antara lain:

- Penggunaan `<list>` pada view (bukan `<tree>` yang sudah usang).
- Constraint didefinisikan melalui `models.Constraint(...)` di dalam `_constraints`
  (bukan `_sql_constraints`).
- `create()` menggunakan decorator `@api.model_create_multi` dengan `vals_list`.
- Visibilitas field/tombol menggunakan atribut `invisible="<ekspresi Python>"`
  (bukan `attrs`/`states`).
- Penghapusan yang dibatasi menggunakan `@api.ondelete(at_uninstall=False)`.

---

## 7. Lisensi

Modul ini dirilis dengan lisensi **LGPL-3**.

**Author:** Najla Haura Mumtazah
