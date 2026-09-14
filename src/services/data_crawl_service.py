from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time

url = "https://vbpl.vn/van-ban/chi-tiet/bo-luat-hinh-su-so-100-2015-qh13--96122"

with sync_playwright() as p:
    # 1. Bỏ cờ headless tự động để tránh bị chặn
    browser = p.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled"]
    )
    
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080}
    )
    
    page = context.new_page()
    print("1. Đang truy cập trang web...")
    page.goto(url, wait_until="domcontentloaded", timeout=60000)

    # Đợi 15 giây cho các script frontend khởi tạo
    time.sleep(15)

    # 2. Chủ động click vào tab 'Toàn văn' nếu có trên giao diện
    try:
        tab_selector = page.locator("text='Toàn văn'").first
        if tab_selector.is_visible():
            print("2. Tìm thấy tab 'Toàn văn', đang click kích hoạt...")
            tab_selector.click()
            time.sleep(3)
    except Exception as e:
        print(f"Bỏ qua bước click tab: {e}")

    # 3. Chờ trạng thái tải tài liệu kết thúc
    print("3. Đang chờ tài liệu render...")
    try:
        # Chờ biến mất dòng chữ 'Đang tải' nếu có
        page.wait_for_selector("text=Đang tải", state="hidden", timeout=10000)
    except Exception:
        pass

    time.sleep(3)

    # 4. Kiểm tra xem nội dung văn bản có nằm trong IFRAME hay không
    extracted_text = ""
    frames = page.frames
    print(f"Tổng số frame phát hiện trên trang: {len(frames)}")

    # Ưu tiên tìm nội dung trong các sub-frames (iframe tài liệu)
    for idx, frame in enumerate(frames):
        try:
            frame_html = frame.content()
            # Kiểm tra xem frame này có chứa các từ khóa đặc trưng của văn bản luật không
            if "Điều 1" in frame_html or "QUỐC HỘI" in frame_html or "BỘ LUẬT" in frame_html:
                print(f"=> Phát hiện nội dung văn bản nằm trong Frame #{idx} (URL: {frame.url[:60]}...)")
                frame_soup = BeautifulSoup(frame_html, "html.parser")
                for tag in frame_soup.select("script, style, nav, header, footer"):
                    tag.decompose()
                extracted_text = frame_soup.get_text(separator="\n", strip=True)
                break
        except Exception:
            continue

    # 5. Nếu không nằm trong frame, lấy từ trang chính
    if not extracted_text:
        print("=> Không tìm thấy trong iframe, tiến hành bóc tách từ DOM chính...")
        main_html = page.content()
        soup = BeautifulSoup(main_html, "html.parser")
        
        for tag in soup.select("script, style, nav, header, footer, .sidebar, #header, #footer"):
            tag.decompose()
            
        extracted_text = soup.get_text(separator="\n", strip=True)

    browser.close()

# 6. Kiểm tra và lưu kết quả
output_path = "bo_luat_hinh_su_so.txt"
if len(extracted_text.strip()) > 500:
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(extracted_text)
    print(f"\n Thành công! Đã trích xuất {len(extracted_text)} ký tự.")
    print(f" File đã lưu tại: {output_path}")
    print("\n--- ĐOẠN ĐẦU VĂN BẢN CÀO ĐƯỢC ---")
    print(extracted_text[:400])
else:
    print("\n Không lấy được dữ liệu hoặc trang trả về rỗng.")
    print(f"Nội dung nhận được: \n{extracted_text}")