from dataclasses import dataclass
from typing import Dict, List


@dataclass
class ToolGroup:
    name: str
    description: str
    tool_names: List[str]
    system_prompt: str


ROUTER_SYSTEM = """Kamu adalah router. Klasifikasikan pesan user ke SATU kategori:

- desktop: buka/tutup/fokus aplikasi, klik, ketik, tekan keyboard
- browser: isi formulir web, buka situs, isi amal yaumi
- package: install/hapus/update software, cari package
- memory: simpan/ingat fakta, todo list, catatan
- youtube: cari/putar lagu, video, musik
- file: baca, tulis, atau hapus file/folder
- display: atur grid overlay layar
- vision: baca teks dari layar atau file gambar (OCR)
- none: sapaan, obrolan biasa, pertanyaan umum, hitungan

Balas HANYA 1 kata: desktop/browser/package/memory/youtube/file/display/vision/none"""


def get_default_groups() -> Dict[str, ToolGroup]:
    return {
        "desktop": ToolGroup(
            name="desktop",
            description="Open/close apps, click, type, keyboard, window management, run commands",
            tool_names=[
                "run_command",
                "open_app",
                "focus_app",
                "close_app",
                "open_url",
                "click",
                "type_text",
                "press_key",
                "hotkey",
                "screen_size",
                "find_element",
                "click_element",
                "list_clickable_elements",
                "get_active_window",
                "find_window",
                "click_window",
                "focus_window",
                "list_windows",
                "x11_click",
                "x11_type",
                "x11_key",
                "x11_hotkey",
                "x11_active_window",
            ],
            system_prompt=(
                "Kamu adalah desktop controller. Tugasmu mengontrol komputer user.\n\n"
                "ATURAN KRITIS:\n"
                "1. Untuk perintah terminal (ls, cat, lspci, df, dll) — gunakan run_command, "
                "JANGAN buka terminal + type_text. run_command langsung eksekusi dan kembali hasilnya\n"
                "2. JANGAN klik buta tanpa melihat layar. Hanya klik kalau ada screen share yang menunjukkan "
                "posisi element. Kalau tidak ada screen share, gunakan find_element/click_element\n"
                "3. Satu tool per langkah. Jangan panggil banyak tool sekaligus\n"
                "4. Setelah run_command, baca hasilnya dan jawab. JANGAN klik-klik lagi\n"
                "5. Gunakan get_active_window untuk cek app apa yang aktif\n"
                "6. Kalau diminta info sistem (GPU, RAM, OS), gunakan run_command dengan perintah yang sesuai\n"
                "7. 🚫 JANGAN klik, ketik, atau sentuh apa pun TANPA perintah EKSPLISIT dari user. "
                "Tunggu user bilang 'klik', 'ketik', 'buka', 'tekan', dulu."
            ),
        ),
        "package": ToolGroup(
            name="package",
            description="Install, remove, update packages and run commands",
            tool_names=[
                "run_command",
                "run_sudo_command",
                "detect_os",
                "update_system",
                "search_packages",
                "get_pkgbuild",
                "install_package",
                "remove_package",
            ],
            system_prompt=(
                "Kamu adalah package manager. Tugasmu install/hapus/update software.\n\n"
                "ATURAN:\n"
                "1. Satu tool per langkah. Jangan multitool\n"
                "2. Sebelum install AUR, cek get_pkgbuild dulu untuk verifikasi\n"
                "3. Gunakan detect_os untuk tahu distro user\n"
                "4. Jalankan perintah satu per satu, baca hasilnya, lanjut"
            ),
        ),
        "browser": ToolGroup(
            name="browser",
            description="Fill web forms, automate browsers, fill Amal Yaumi on SIS Al Uswah",
            tool_names=[
                "open_app",
                "search_youtube",
                "play_youtube",
                "browser_navigate",
                "browser_snapshot",
                "browser_fill_by_label",
                "browser_select_by_label",
                "browser_click_by_text",
                "browser_screenshot",
                "browser_close",
                "browser_status",
                "browser_save_form_data",
                "browser_load_form_data",
                "amal_yaumi_fill",
            ],
            system_prompt=(
                "Kamu adalah browser agent. Tugasmu mengisi formulir web dan "
                "mengotomasi browser menggunakan Chromium.\n\n"
                "ATURAN:\n"
                "1. Navigasi dulu dengan browser_navigate, lalu cek struktur form "
                "dengan browser_snapshot\n"
                "2. Isi field pakai browser_fill_by_label / browser_select_by_label "
                "dengan label yang terlihat di halaman\n"
                "3. Klik tombol pakai browser_click_by_text\n"
                "4. Untuk Amal Yaumi SIS Al Uswah, gunakan amal_yaumi_fill dengan "
                "entries berisi pekanName + data sholat & extras\n"
                "5. Simpan data formulir yang dijawab user sekali dengan "
                "browser_save_form_data supaya bisa dipakai lagi\n"
                "6. Satu tool per langkah, baca hasilnya sebelum lanjut"
            ),
        ),
        "memory": ToolGroup(
            name="memory",
            description="Store memories, manage todo list",
            tool_names=[
                "store_memory",
                "add_todo",
                "list_todos",
                "delete_todo",
                "update_todo",
            ],
            system_prompt=(
                "Kamu adalah memory keeper. Tugasmu menyimpan fakta tentang user "
                "dan mengelola todo list. Gunakan tool sesuai perintah. Satu tool per langkah."
            ),
        ),
        "youtube": ToolGroup(
            name="youtube",
            description="Search and play YouTube videos, manage music playlists",
            tool_names=[
                "search_youtube",
                "play_youtube",
                "play_mv",
                "list_playlists",
                "create_playlist",
                "delete_playlist",
                "rename_playlist",
                "add_to_playlist",
                "remove_from_playlist",
                "download_to_playlist",
                "play_playlist",
            ],
            system_prompt=(
                "Kamu adalah YouTube player. Tugasmu mencari dan memutar lagu/video dari YouTube "
                "serta mengelola playlist musik.\n\n"
                "ATURAN:\n"
                "1. Cari dulu dengan search_youtube\n"
                "2. Pilih hasil paling relevan\n"
                "3. Putar dengan play_youtube\n"
                "4. Jangan putar lagu yang sama atau mirip dengan yang baru diputar\n"
                "5. Untuk playlist: list_playlists untuk melihat daftar, create_playlist untuk membuat, "
                "add_to_playlist untuk menambah lagu, play_playlist untuk memutar (bisa shuffle=True), "
                "remove_from_playlist / delete_playlist / rename_playlist untuk mengedit"
            ),
        ),
        "file": ToolGroup(
            name="file",
            description="Read, write, and delete files and directories",
            tool_names=["read_file", "write_file", "delete_file"],
            system_prompt=(
                "Kamu adalah file manager. Tugasmu membaca, menulis, dan menghapus "
                "file atau direktori di komputer user.\n\n"
                "ATURAN:\n"
                "1. read_file untuk membaca isi file (aman, langsung jalan)\n"
                "2. write_file untuk menulis/membuat file — operasi ini akan meminta "
                "persetujuan user (diff akan ditampilkan). Jika user menolak, jangan "
                "memaksa, jelaskan kenapa perlu menulis file tersebut.\n"
                "3. delete_file untuk menghapus — operasi ini akan meminta persetujuan "
                "user. Gunakan recursive=true hanya jika benar-benar perlu menghapus "
                "folder beserta isinya.\n"
                "4. Selalu baca file dulu sebelum menimpa agar diff yang tampil akurat."
            ),
        ),
        "display": ToolGroup(
            name="display",
            description="Grid overlay settings",
            tool_names=["set_grid_spec", "disable_grid_overlay"],
            system_prompt=(
                "Kamu adalah display controller. Tugasmu mengatur grid overlay "
                "pada tampilan screen share."
            ),
        ),
        "vision": ToolGroup(
            name="vision",
            description="Read text from the screen or from image files (OCR)",
            tool_names=["ocr_screen", "ocr_image"],
            system_prompt=(
                "Kamu adalah vision agent. Tugasmu membaca teks dari layar "
                "atau file gambar menggunakan OCR. Gunakan ocr_screen untuk "
                "membaca apa yang tampil di layar, ocr_image untuk membaca "
                "teks dari file gambar."
            ),
        ),
    }


SIMPLE_TOOL_NAMES = [
    # Web
    "web_search",
    "search_news",
    "web_fetch",
    # Information
    "weather",
    "system_status",
    "take_screenshot",
    "wikipedia_search",
    # Memory & Todo
    "store_memory",
    "add_todo",
    "list_todos",
    "delete_todo",
    "update_todo",
    # YouTube
    "search_youtube",
    "play_youtube",
    "play_mv",
    "list_playlists",
    "create_playlist",
    "delete_playlist",
    "rename_playlist",
    "add_to_playlist",
    "remove_from_playlist",
    "download_to_playlist",
    "play_playlist",
    # Navigation & display
    "open_app",
    "open_url",
    "screen_size",
    "detect_os",
    "set_grid_spec",
    "disable_grid_overlay",
    "get_active_window",
    # Browser / form automation
    "browser_navigate",
    "browser_snapshot",
    "browser_fill_by_label",
    "browser_select_by_label",
    "browser_click_by_text",
    "browser_screenshot",
    "browser_close",
    "browser_status",
    "browser_save_form_data",
    "browser_load_form_data",
    "amal_yaumi_fill",
    # Vision / OCR
    "ocr_screen",
    "ocr_image",
    # File operations (read is safe; write/delete require user approval)
    "read_file",
    "write_file",
    "delete_file",
]


def get_summon_specialist_tool() -> dict:
    """Tool definition for Gemini to summon specialist Groq agents."""
    return {
        "type": "function",
        "function": {
            "name": "summon_specialist",
            "description": (
                "⚠️ TOOL INI HANYA UNTUK AKSI NYATA. JANGAN GUNAKAN UNTUK CHAT.\n\n"
                "GUNAKAN summon_specialist HANYA KALAU user meminta:\n"
                "- Buka/tutup aplikasi → group: desktop\n"
                "- Isi formulir web / amal yaumi → group: browser\n"
                "- Install/update/hapus software → group: package\n"
                "- Simpan fakta tentang user → group: memory\n"
                "- Putar musik/video → group: youtube\n"
                "- Hapus file → group: file\n"
                "- Baca teks dari layar/gambar → group: vision\n\n"
                "❌ JANGAN GUNAKAN summon_specialist untuk:\n"
                "- Chat/obrolan santai ('ok', 'fairs', 'gpp', 'hmm', 'wrong', 'bahahaha')\n"
                "- Opini/lelucon/roasting/sarkasme\n"
                "- Pertanyaan retoris atau tebakan\n"
                "- Respon emosi ('sedih', 'marah', 'seneng')\n"
                "- Apa pun yang bisa dijawab tanpa tool\n"
                "- 🚫 JANGAN klik/ketik/sentuh layar TANPA perintah EKSPLISIT. "
                "Tunggu user bilang 'klik', 'ketik', 'buka'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "group": {
                        "type": "string",
                        "enum": [
                            "desktop",
                            "browser",
                            "package",
                            "memory",
                            "youtube",
                            "file",
                            "display",
                            "vision",
                        ],
                        "description": "Specialist group: desktop, package, memory, youtube, file, display, vision",
                    },
                    "request": {
                        "type": "string",
                        "description": (
                            "Instruksi detail untuk specialist dalam Bahasa Indonesia"
                        ),
                    },
                },
                "required": ["group", "request"],
            },
        },
    }


def filter_tool_definitions(
    all_tools: List[dict],
    group: ToolGroup,
) -> List[dict]:
    """Filter tool definitions to only include those in the given group."""
    names = set(group.tool_names)
    return [t for t in all_tools if t.get("function", {}).get("name") in names]
