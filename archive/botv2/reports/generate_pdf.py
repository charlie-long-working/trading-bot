from fpdf import FPDF
import os

FONT_DIR = "/System/Library/Fonts/Supplemental/"
FONT_REGULAR = os.path.join(FONT_DIR, "Arial Unicode.ttf")
FONT_BOLD = FONT_REGULAR

if not os.path.exists(FONT_REGULAR):
    for candidate in [
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/SFNS.ttf",
    ]:
        if os.path.exists(candidate):
            FONT_REGULAR = candidate
            FONT_BOLD = candidate
            break


class PDF(FPDF):
    def header(self):
        pass

    def footer(self):
        self.set_y(-15)
        self.set_font("vn", "", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Trang {self.page_no()}/{{nb}}", align="C")


pdf = PDF(orientation="P", unit="mm", format="A4")
pdf.alias_nb_pages()
pdf.set_auto_page_break(auto=True, margin=20)

pdf.add_font("vn", "", FONT_REGULAR, uni=True)
pdf.add_font("vn", "B", FONT_BOLD, uni=True)

LM = 15
RM = 15
PW = 210 - LM - RM


def add_title(text):
    pdf.set_font("vn", "B", 20)
    pdf.set_text_color(178, 34, 34)
    pdf.cell(0, 12, text, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(178, 34, 34)
    pdf.set_line_width(0.8)
    pdf.line(LM, pdf.get_y(), 210 - RM, pdf.get_y())
    pdf.ln(6)


def add_h2(text):
    pdf.ln(4)
    pdf.set_font("vn", "B", 14)
    pdf.set_text_color(26, 82, 118)
    pdf.set_fill_color(26, 82, 118)
    pdf.rect(LM, pdf.get_y(), 3, 8, "F")
    pdf.set_x(LM + 5)
    pdf.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)


def add_h3(text, star=False):
    pdf.ln(2)
    pdf.set_font("vn", "B", 12)
    pdf.set_text_color(192, 57, 43)
    prefix = "★ " if star else ""
    pdf.cell(0, 7, f"{prefix}{text}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)


def add_text(text, bold=False, size=10, color=(34, 34, 34)):
    pdf.set_font("vn", "B" if bold else "", size)
    pdf.set_text_color(*color)
    pdf.multi_cell(PW, 5.5, text, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def add_bullet(text, indent=0):
    pdf.set_font("vn", "", 10)
    pdf.set_text_color(34, 34, 34)
    x = LM + 5 + indent
    pdf.set_x(x)
    pdf.cell(5, 5.5, "•")
    pdf.multi_cell(PW - 10 - indent, 5.5, text, new_x="LMARGIN", new_y="NEXT")


def add_table(headers, rows, col_widths=None):
    if col_widths is None:
        col_widths = [PW / len(headers)] * len(headers)

    pdf.set_font("vn", "B", 9)
    pdf.set_fill_color(26, 82, 118)
    pdf.set_text_color(255, 255, 255)
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 7, h, border=1, fill=True, align="C")
    pdf.ln()

    pdf.set_font("vn", "", 9)
    fill = False
    for row in rows:
        if fill:
            pdf.set_fill_color(242, 247, 251)
        else:
            pdf.set_fill_color(255, 255, 255)
        pdf.set_text_color(34, 34, 34)

        max_lines = 1
        for i, cell in enumerate(row):
            lines = pdf.multi_cell(col_widths[i], 6, str(cell), dry_run=True, output="LINES")
            max_lines = max(max_lines, len(lines))
        row_h = max_lines * 6

        x_start = pdf.get_x()
        y_start = pdf.get_y()

        if y_start + row_h > 280:
            pdf.add_page()
            y_start = pdf.get_y()

        for i, cell in enumerate(row):
            x = x_start + sum(col_widths[:i])
            pdf.set_xy(x, y_start)
            if fill:
                pdf.set_fill_color(242, 247, 251)
            else:
                pdf.set_fill_color(255, 255, 255)
            pdf.rect(x, y_start, col_widths[i], row_h, "F")
            pdf.rect(x, y_start, col_widths[i], row_h, "D")
            pdf.set_xy(x + 1, y_start + 1)
            pdf.multi_cell(col_widths[i] - 2, 6, str(cell))

        pdf.set_xy(x_start, y_start + row_h)
        fill = not fill
    pdf.ln(3)


def add_note(text):
    pdf.ln(2)
    pdf.set_fill_color(255, 243, 205)
    pdf.set_draw_color(255, 193, 7)
    y = pdf.get_y()
    pdf.rect(LM, y, PW, 12, "FD")
    pdf.set_line_width(0.5)
    pdf.line(LM, y, LM, y + 12)
    pdf.set_xy(LM + 3, y + 1)
    pdf.set_font("vn", "", 9)
    pdf.set_text_color(100, 80, 0)
    pdf.multi_cell(PW - 6, 5, text)
    pdf.ln(4)


def add_separator():
    pdf.ln(2)
    pdf.set_draw_color(200, 200, 200)
    pdf.set_line_width(0.3)
    pdf.line(LM + 20, pdf.get_y(), 210 - RM - 20, pdf.get_y())
    pdf.ln(4)

# ========== PAGE 1: TITLE ==========
pdf.add_page()
pdf.set_left_margin(LM)
pdf.set_right_margin(RM)

add_title("CHỌN NGÀY NHẬP HỌC MẦM NON CHO BÉ")

pdf.set_font("vn", "", 10)
pdf.set_text_color(80, 80, 80)
pdf.cell(0, 6, "Bé trai sinh: 01/12/2024 (dương lịch) — Mùng 1 tháng 11 âm lịch năm Giáp Thìn", new_x="LMARGIN", new_y="NEXT")
pdf.cell(0, 6, "Con giáp: Thìn (Rồng)  |  Mệnh: Phú Đăng Hỏa (Lửa đèn)", new_x="LMARGIN", new_y="NEXT")
pdf.cell(0, 6, "Ngày lập: 16/03/2026", new_x="LMARGIN", new_y="NEXT")
pdf.ln(4)

# ========== SECTION 1 ==========
add_h2("1. NGUYÊN TẮC CHỌN NGÀY CHO BÉ TUỔI THÌN")

add_h3("Nên chọn")
add_bullet("Ngày Hoàng đạo (Thanh Long, Minh Đường, Kim Quỹ, Ngọc Đường, Tư Mệnh, Kim Đường)")
add_bullet("Ngày tam hợp với Thìn: Tý (Chuột), Thân (Khỉ) — hợp Thuỷ cục")
add_bullet("Ngày lục hợp với Thìn: Dậu (Gà)")
add_bullet("Ngày hành Mộc hoặc Thổ (tương sinh mệnh Hỏa)")

add_h3("Nên tránh")
add_bullet("Ngày xung Thìn: ngày Tuất (Chó) — tuyệt đối tránh")
add_bullet("Tam Nương: mùng 3, 7, 13, 18, 22, 27 âm lịch")
add_bullet("Nguyệt Kỵ: mùng 5, 14, 23 âm lịch")
add_bullet("Hung thần: Sát Chủ, Nguyệt Phá, Dương Công Kỵ")

# ========== SECTION 2 ==========
add_h2("2. THÁNG NÀO NÊN CHO TRẺ ĐI HỌC?")

add_h3("Tháng lý tưởng: Tháng 4, 5, 6 (Xuân - đầu Hè)")
add_table(
    ["Yếu tố", "Lý do"],
    [
        ["Thời tiết", "Ấm áp, ít mưa — bé ít cảm lạnh"],
        ["Dịch bệnh", "Đã qua mùa cúm (tháng 12-3)"],
        ["Tâm lý", "Ngày dài, nắng sáng — bé vui hơn"],
        ["Sĩ số lớp", "Giữa năm học, lớp ít bé — cô chăm kỹ"],
    ],
    [45, PW - 45],
)

add_h3("Tháng nên tránh: Tháng 10-12, 1-2")
add_table(
    ["Lý do", "Chi tiết"],
    [
        ["Mùa dịch", "T10-11: tay chân miệng. T12-2: cúm, viêm phổi"],
        ["Thời tiết lạnh", "Miễn dịch bị tấn công kép"],
        ["Tâm lý", "Ngày ngắn, trời tối sớm — bé dễ buồn"],
    ],
    [45, PW - 45],
)

# ========== SECTION 3 ==========
add_h2("3. KẾT QUẢ — THÁNG 3/2026")

add_h3("Ngày đẹp nhất: Thứ Hai 30/3/2026")
add_table(
    ["Thông tin", "Chi tiết"],
    [
        ["Âm lịch", "12/2 năm Bính Ngọ, ngày Quý Mão"],
        ["Hoàng đạo", "MINH ĐƯỜNG — năng lượng tích cực"],
        ["Trực", "KIẾN — cường kiện, kiện tráng"],
        ["Bảo Nhật", "Can sinh Chi (rất tốt)"],
        ["Lục diệu", "ĐẠI AN — bền vững, yên ổn"],
        ["Xếp hạng", "1 trong 2 ngày đẹp nhất tháng 3"],
        ["Giờ tốt", "5h-7h Ất Mão (Minh Đường)"],
    ],
    [45, PW - 45],
)
add_note("Lưu ý: Bé mới 16 tháng vào tháng 3, chưa đủ 18 tháng theo quy định nhà trẻ.")

# ========== SECTION 4 ==========
add_h2("4. KẾT QUẢ — THÁNG 5/2026 (bé ~17 tháng)")

add_h3("TOP 1: Thứ Hai 11/5/2026", star=True)
add_table(
    ["Thông tin", "Chi tiết"],
    [
        ["Can chi", "Ất Dậu"],
        ["Hoàng đạo", "KIM ĐƯỜNG — phúc thần, dễ thành công"],
        ["Trực", "ĐỊNH — an định, ổn định"],
        ["Điểm đặc biệt", "Dậu LỤC HỢP với Thìn"],
        ["Cát thần", "Thiên Quý + Tốc Hỷ"],
        ["Hung thần", "KHÔNG CÓ"],
        ["Giờ tốt", "5h-7h Kỷ Mão (Minh Đường)"],
    ],
    [45, PW - 45],
)

add_h3("TOP 2: Thứ Tư 27/5/2026")
add_table(
    ["Thông tin", "Chi tiết"],
    [
        ["Can chi", "Tân Sửu"],
        ["Hoàng đạo", "NGỌC ĐƯỜNG — tốt cho tài năng, thi cử"],
        ["Trực", "THÀNH — thành công, thành tựu (đại cát!)"],
        ["Cát thần", "Thiên Thành + Thiên Đức"],
        ["Xếp hạng", "Ngày đẹp nhất tháng 5 (saptet.com)"],
        ["Giờ tốt", "5h-7h Tân Mão (Kim Đường)"],
    ],
    [45, PW - 45],
)

add_h3("TOP 3: Thứ Tư 20/5/2026")
add_table(
    ["Thông tin", "Chi tiết"],
    [
        ["Can chi", "Giáp Ngọ"],
        ["Hoàng đạo", "THANH LONG — hỷ sự, may mắn, thi cử"],
        ["Cát thần", "Bảo Nhật + Đại An"],
        ["Hung thần", "KHÔNG CÓ"],
        ["Giờ tốt", "5h-7h Đinh Mão (Ngọc Đường)"],
    ],
    [45, PW - 45],
)

# ========== SECTION 5 ==========
add_h2("5. KẾT QUẢ — THÁNG 6/2026 (bé ~18 tháng)")

add_h3("TOP 1: Thứ Hai 15/6/2026 — KHUYẾN NGHỊ SỐ 1", star=True)
add_table(
    ["Thông tin", "Chi tiết"],
    [
        ["Can chi", "Canh Thân"],
        ["Hoàng đạo", "THANH LONG — hỷ sự, may mắn, thi cử"],
        ["Trực", "MÃN — phong thu, mỹ mãn"],
        ["Điểm đặc biệt", "Thân TAM HỢP với Thìn (hợp cực mạnh!)"],
        ["Cát thần", "Lộc Khố + Tiểu Cát"],
        ["Hung thần", "KHÔNG CÓ"],
        ["Giờ tốt", "7h-9h Canh Thìn (Kim Quỹ)"],
        ["Tuổi bé", "~18.5 tháng — đủ tuổi nhà trẻ"],
    ],
    [45, PW - 45],
)

add_text("Lý do đây là ngày tốt nhất:", bold=True, size=10, color=(178, 34, 34))
add_bullet("Thân-Tý-Thìn tam hợp (mạnh nhất trong các loại hợp)")
add_bullet("Thanh Long hoàng đạo (đặc biệt tốt cho thi cử, học hành)")
add_bullet("Hoàn toàn không có hung thần")
add_bullet("Thứ Hai = đầu tuần, hợp \"khai học\"")
add_bullet("Bé đã đủ 18 tháng tuổi")
add_bullet("Giờ hoàng đạo 7h-9h rất thuận tiện cho giờ đến trường")

add_h3("TOP 2: Thứ Năm 11/6/2026")
add_table(
    ["Thông tin", "Chi tiết"],
    [
        ["Can chi", "Bính Thìn"],
        ["Hoàng đạo", "TƯ MỆNH — trợ giúp bản mệnh"],
        ["Trực", "KHAI — khai thủy, khai triển (hợp khai học!)"],
        ["Cát thần", "Bảo Nhật + Thiên Đức Hợp + Thiên Quý"],
        ["Giờ tốt", "7h-9h Nhâm Thìn (Thanh Long)"],
    ],
    [45, PW - 45],
)

add_h3("TOP 3: Thứ Hai 1/6/2026 — Ngày Quốc tế Thiếu nhi")
add_table(
    ["Thông tin", "Chi tiết"],
    [
        ["Can chi", "Bính Ngọ"],
        ["Hoàng đạo", "THANH LONG"],
        ["Cát thần", "Thiên Đức Hợp + Thiên Quý + U Vi Tinh + Đại An"],
        ["Ý nghĩa", "Ngày Thiếu nhi + bé tròn 18 tháng"],
        ["Giờ tốt", "5h-7h Tân Mão (Ngọc Đường)"],
    ],
    [45, PW - 45],
)

add_h3("TOP 4: Thứ Năm 25/6/2026")
add_table(
    ["Thông tin", "Chi tiết"],
    [
        ["Can chi", "Canh Ngọ"],
        ["Hoàng đạo", "TƯ MỆNH"],
        ["Trực", "KIẾN — cường kiện"],
        ["Xếp hạng", "Ngày đẹp nhất tháng 6 (saptet.com)"],
        ["Hung thần", "KHÔNG CÓ"],
        ["Giờ tốt", "5h-7h Kỷ Mão (Ngọc Đường)"],
    ],
    [45, PW - 45],
)

# ========== SECTION 6 ==========
add_h2("6. CÁC NGÀY PHẢI TRÁNH (DÙ HOÀNG ĐẠO)")

add_table(
    ["Ngày", "Can chi", "Lý do"],
    [
        ["24/5/2026", "Mậu Tuất", "XUNG THÌN trực tiếp"],
        ["5/6/2026", "Canh Tuất", "XUNG THÌN — ghi rõ 'Tuổi xung: Giáp Thìn'"],
        ["30/5/2026", "Giáp Thìn", "Phạt Nhật + Nguyệt Kỵ"],
        ["19/6/2026", "Giáp Tý", "Nguyệt Kỵ + Dương Công Kỵ + Nguyệt Phá"],
    ],
    [30, 30, PW - 60],
)

# ========== SECTION 7 ==========
add_h2("7. CHUẨN BỊ SỨC KHỎE CHO BÉ")

add_h3("Giai đoạn ốm thường gặp khi mới đi học")
add_table(
    ["Giai đoạn", "Thời gian", "Mô tả"],
    [
        ["2 tuần đầu", "Tuần 1-2", "Stress, quấy khóc, biếng ăn"],
        ["Tháng 1-3", "Tháng 1 đến 3", "ỐM NHIỀU NHẤT — 2-3 lần/tháng"],
        ["Tháng 3-6", "Tháng 3 đến 6", "Giảm dần, ~1 lần/tháng"],
        ["Sau 6 tháng", "Từ T6 trở đi", "Miễn dịch ổn, ốm ít rõ rệt"],
    ],
    [35, 35, PW - 70],
)

add_h3("Mẹo giảm ốm")
add_bullet("Tiêm phòng đầy đủ (đặc biệt cúm, phế cầu)")
add_bullet("Rửa mũi bằng nước muối sinh lý mỗi tối")
add_bullet("Thay quần áo ngay khi về nhà")
add_bullet("Ngủ đủ giấc (12-14 tiếng/ngày cho bé 16-18 tháng)")
add_bullet("Khi ốm, cho nghỉ ở nhà đến khi hết hẳn")

add_h3("Đưa bé đi khám ngay khi")
add_bullet("Sốt trên 39°C kéo dài hơn 48h")
add_bullet("Bé bỏ ăn/bú hoàn toàn")
add_bullet("Thở nhanh, khó thở, rút lõm ngực")
add_bullet("Nổi bóng nước ở tay/chân/miệng")
add_bullet("Bé lừ đừ, li bì bất thường")

# ========== SECTION 8 ==========
add_h2("8. LỊCH CHUẨN BỊ GỢI Ý")

add_table(
    ["Thời gian", "Việc làm"],
    [
        ["Tháng 4-5/2026", "Tham quan, đăng ký trường, nộp hồ sơ"],
        ["Đầu tháng 6", "Cho bé đến trường làm quen 1-2 buổi"],
        ["15/6/2026", "NGÀY CHÍNH THỨC ĐI HỌC ĐẦU TIÊN"],
        ["Tuần 1-2", "Đưa đón đúng giờ, cho bé đi nửa ngày"],
        ["Từ tuần 3", "Chuyển sang cả ngày khi bé đã quen"],
    ],
    [40, PW - 40],
)

# ========== CONCLUSION ==========
add_separator()
pdf.ln(2)
pdf.set_font("vn", "B", 14)
pdf.set_text_color(178, 34, 34)
pdf.cell(0, 8, "KẾT LUẬN", align="C", new_x="LMARGIN", new_y="NEXT")
pdf.ln(3)

add_text("Ngày nhập học khuyến nghị: Thứ Hai, 15/6/2026 (1/5 âm lịch)", bold=True, size=11, color=(26, 82, 118))
add_text("Giờ đưa bé đến trường: 7h-9h sáng (giờ Thìn — Kim Quỹ Hoàng đạo)", bold=True, size=11, color=(26, 82, 118))
add_text("Hướng xuất hành: Tây Nam (Tài Thần) hoặc Tây Bắc (Hỷ Thần)", bold=True, size=11, color=(26, 82, 118))

pdf.ln(4)
add_note("Thông tin phong thuỷ mang tính tham khảo dựa trên lịch vạn niên. Nên kết hợp tham khảo thầy phong thuỷ uy tín nếu muốn phân tích sâu hơn (bát tự, tứ trụ).")

pdf.ln(3)
pdf.set_font("vn", "", 8)
pdf.set_text_color(150, 150, 150)
pdf.cell(0, 5, "Nguồn dữ liệu: saptet.com, lichngaytot.com, ngaydep.com — Tra cứu ngày 16/03/2026", align="C")

OUTPUT = "chon_ngay_nhap_hoc_be.pdf"
pdf.output(OUTPUT)
print(f"PDF created successfully: {os.path.abspath(OUTPUT)}")
