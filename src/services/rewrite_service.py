import re
import os
import datetime

def extract_metadata(lines):
    """
    Hàm trích xuất metadata từ phần đầu của văn bản.
    """
    metadata = {
        "ten_bo_luat": "Chưa xác định",
        "so_hieu": "Chưa xác định",
        "ngay_ban_hanh": "Chưa xác định",
        "ngay_co_hieu_luc": "Chưa xác định",
        "ngay_cap_nhat": "Chưa xác định",
        "ngay_het_hieu_luc": "Chưa xác định",
        "muc_luc": []
    }
    
    # Tìm kiếm các thông tin trong khoảng 50 dòng đầu tiên
    for i in range(min(50, len(lines))):
        line = lines[i].strip()
        
        # Tên bộ luật (thường viết hoa)
        if "BỘ LUẬT" in line and not line.startswith("Bộ luật số:"):
            # Nối dòng nếu tên bị rớt dòng (VD: BỘ LUẬT \n LAO ĐỘNG)
            if i + 1 < len(lines) and lines[i+1].strip().isupper():
                metadata["ten_bo_luat"] = f"{line} {lines[i+1].strip()}"
            elif metadata["ten_bo_luat"] == "Chưa xác định":
                metadata["ten_bo_luat"] = line

        # Số hiệu
        if "số:" in line.lower() or "số " in line.lower():
            match = re.search(r'số:?\s*([A-Za-z0-9/]+)', line, re.IGNORECASE)
            if match:
                metadata["so_hieu"] = match.group(1)
        
        # Ngày ban hành (VD: Hà Nội, ngày 20 tháng 11 năm 2019)
        match_ban_hanh = re.search(r'ngày\s+(\d+)\s+tháng\s+(\d+)\s+năm\s+(\d+)', line.lower())
        if match_ban_hanh:
            metadata["ngay_ban_hanh"] = f"{match_ban_hanh.group(1)}/{match_ban_hanh.group(2)}/{match_ban_hanh.group(3)}"
            
        # Ngày có hiệu lực
        if "ngày có hiệu lực:" in line.lower():
            if i + 1 < len(lines):
                metadata["ngay_co_hieu_luc"] = lines[i+1].strip()
                
        # Ngày cập nhật
        if "ngày cập nhật:" in line.lower():
            if i + 1 < len(lines):
                metadata["ngay_cap_nhat"] = lines[i+1].strip()
                
        # Tình trạng hiệu lực (Hết hiệu lực một phần / Toàn bộ)
        if "hết hiệu lực" in line.lower():
            metadata["ngay_het_hieu_luc"] = line

    return metadata

def convert_vbpl_txt_to_md(input_file, output_file):
    """
    Hàm đọc file txt, lọc nhiễu, cấu trúc lại thành markdown và xuất file.
    Trả về đường dẫn đến file output.
    """
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Không tìm thấy file: {input_file}")

    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    metadata = extract_metadata(lines)
    
    # Từ khóa rác từ giao diện website cần loại bỏ
    garbage_words = [
        "Nội dung", "Thuộc tính", "Lược đồ", "Lịch sử", "Văn bản gốc", "Tải về", 
        "100%", "Hiển thị chi tiết cập nhật", "QUỐC HỘI", "--------", 
        "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", "Độc lập - Tự do - Hạnh phúc", "---------------"
    ]

    processed_lines = []
    toc = []
    
    i = 0
    in_content_area = False

    while i < len(lines):
        line = lines[i].strip()
        
        # Bỏ qua dòng trống hoặc từ khóa giao diện
        if not line or line in garbage_words:
            i += 1
            continue

        # Bắt đầu xử lý nội dung chính từ "Chương I" hoặc "Căn cứ..."
        if line.startswith("Căn cứ") or line.startswith("Chương I"):
            in_content_area = True

        if not in_content_area:
            i += 1
            continue

        # 1. Xử lý Chương (Chapter) -> Header 1
        if re.match(r'^Chương\s+[IVXLCDM]+', line, re.IGNORECASE):
            header_text = line
            # Kiểm tra xem tên chương có ở dòng tiếp theo không (viết hoa)
            if i + 1 < len(lines):
                next_line = lines[i+1].strip()
                if next_line.isupper() and not re.match(r'^(Điều|Mục)\s+', next_line, re.IGNORECASE):
                    header_text += f": {next_line}"
                    i += 1 # Bỏ qua dòng tên chương
            processed_lines.append(f"\n# {header_text}\n")
            toc.append(header_text)
            
        # 2. Xử lý Mục (Section) -> Header 2
        elif re.match(r'^Mục\s+\d+', line, re.IGNORECASE):
            header_text = line
            # Nối tên mục nếu nó nằm ở dòng dưới
            if i + 1 < len(lines):
                next_line = lines[i+1].strip()
                if next_line.isupper() and not re.match(r'^Điều\s+', next_line, re.IGNORECASE):
                    header_text += f": {next_line}"
                    i += 1
            processed_lines.append(f"\n## {header_text}\n")
            toc.append(f"  - {header_text}")
            
        # 3. Xử lý Điều (Article) -> Header 3
        elif re.match(r'^Điều\s+\d+\.', line, re.IGNORECASE):
            processed_lines.append(f"\n### {line}\n")
            toc.append(f"    - {line}")
            
        # 4. Xử lý Khoản (Clause) - Bôi đậm số khoản (Ví dụ: 1. , 2.)
        elif re.match(r'^\d+\.', line):
            # Tách số khoản và nội dung nếu chúng dính liền
            match = re.match(r'^(\d+\.)\s*(.*)', line)
            if match:
                processed_lines.append(f"\n**{match.group(1)}** {match.group(2)}")
            else:
                processed_lines.append(line)
                
        # 5. Xử lý Điểm (Point) - (Ví dụ: a), b), c))
        elif re.match(r'^[a-zđ]\)', line):
            processed_lines.append(f"{line}")
            
        # 6. Nội dung văn bản bình thường
        else:
            # Nếu là câu kết thúc bằng chữ cái thường và dòng tiếp theo cũng không phải cấu trúc mới
            # thì nối dòng để chunker dễ đọc hơn (tuỳ chọn, nhưng ở đây giữ nguyên gốc bằng cách thêm khoảng trắng)
            processed_lines.append(f"{line}")
            
        i += 1

    # Cập nhật Mục lục vào metadata
    metadata["muc_luc"] = toc

    # --- XÂY DỰNG FILE MARKDOWN FINAL ---
    md_content = []
    
    # Ghi YAML Metadata (Frontmatter)
    md_content.append("---")
    md_content.append(f"title: \"{metadata['ten_bo_luat']}\"")
    md_content.append(f"number: \"{metadata['so_hieu']}\"")
    md_content.append(f"effective_date: \"{metadata['ngay_co_hieu_luc']}\"")
    md_content.append(f"promulgation_date: \"{metadata['ngay_ban_hanh']}\"")
    md_content.append(f"expiration_date: \"{metadata['ngay_het_hieu_luc']}\"")
    md_content.append(f"update_date: \"{metadata['ngay_cap_nhat']}\"")
    md_content.append("table_of_contents:")
    for item in metadata["muc_luc"]:
        # Chuyển đổi định dạng list cho YAML
        if item.startswith("  -"):
            md_content.append(f"  {item}")
        elif item.startswith("    -"):
            md_content.append(f"    {item}")
        else:
            md_content.append(f"  - {item}")
    md_content.append("---\n")
    
    # Ghi nội dung đã được xử lý
    md_content.append("\n".join(processed_lines))
    
    # Lưu ra file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(md_content))
        
    print(f"Đã chuyển đổi thành công! Output lưu tại: {os.path.abspath(output_file)}")
    return os.path.abspath(output_file)

# --- Khối chạy thử script (Entry Point) ---
if __name__ == "__main__":
    # Thay đổi tên file input/output cho phù hợp với môi trường của bạn
    input_txt_path = "bo_luat_lao_dong_vbpl.txt" 
    output_md_path = "bo_luat_lao_dong_vbpl_structured.md"
    
    try:
        # Giả lập tạo file input từ dữ liệu prompt nếu file chưa tồn tại (để bạn dễ test)
        if not os.path.exists(input_txt_path):
            print(f"Vui lòng đảm bảo file '{input_txt_path}' nằm cùng thư mục với script.")
        else:
            result_path = convert_vbpl_txt_to_md(input_txt_path, output_md_path)
    except Exception as e:
        print(f"Đã xảy ra lỗi: {e}")