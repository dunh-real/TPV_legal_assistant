import os
import re
import json
import yaml
from uuid import uuid4
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

class ChunkingService:
    def __init__(self, md_file_path):
        self.md_file_path = md_file_path
        
        # cau hinh chia cat theo cau truc markdown
        self.headers_to_split_on = [
            ("#", "Chương"),
            ("##", "Mục"),
            ("###", "Điều")
        ]
        self.md_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on = self.headers_to_split_on,
            strip_headers = False
        )
        
        # cấu hình chia cắt child chunk (small chunks cho qdrant)
        # sử dụng recursivecharacter để cắt theo khoản, điểm hoặc câu
        self.child_splitter = RecursiveCharacterTextSplitter(
            chunk_size = 400,
            chunk_overlap = 50,
            separators = ["\n\n", "\n", ".", ";"]
        )
    
    def _extract_frontmatter_and_content(self, text):
        """Tách metadata (YAML) và nội dung chính của file Markdown, hỗ trợ trích xuất đầy đủ các trường."""
        match = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
        if match:
            metadata_str = match.group(1)
            content = match.group(2)
            try:
                # Thử parse bằng YAML chuẩn
                metadata = yaml.safe_load(metadata_str)
                if not isinstance(metadata, dict):
                    metadata = {}
            except yaml.YAMLError:
                print("⚠️ Cảnh báo: Cấu trúc YAML không chuẩn (có thể do mục lục), đang dùng bộ trích xuất dự phòng...")
                metadata = {}
                
                # Danh sách các trường metadata cần trích xuất
                keys_to_extract = [
                    "title", 
                    "number", 
                    "effective_date", 
                    "promulgation_date", 
                    "expiration_date", 
                    "update_date"
                ]
                
                # Dùng Regex để quét từng trường (hỗ trợ cả có và không có dấu ngoặc kép)
                for key in keys_to_extract:
                    # Biểu thức chính quy tìm: key: "value" hoặc key: value
                    pattern = rf"^{key}\s*:\s*[\"']?(.*?)[\"']?\s*$"
                    regex_match = re.search(pattern, metadata_str, re.IGNORECASE | re.MULTILINE)
                    if regex_match:
                        metadata[key] = regex_match.group(1).strip()
                        
            return metadata, content
        return {}, text
    
    def process(self):
        with open(self.md_file_path, 'r', encoding = 'utf-8') as f:
            raw_text = f.read()
        
        law_metadata, main_content = self._extract_frontmatter_and_content(raw_text)
        
        # Bước 1: tạo parent chunks
        # cắt chính xác theo từng điều luật
        parent_docs = self.md_splitter.split_text(main_content)
        
        qdrant_payloads = []
        redis_payloads = {}
        
        for doc in parent_docs:
            parent_id = str(uuid4())
            parent_text = doc.page_content
            
            # kế thừa metadata cấu trúc từ markdown (chương, mục, điều)
            doc_metadata = doc.metadata.copy()
            # gắn thêm metadata chung của bộ luật
            doc_metadata["Luật"] = law_metadata.get("title", "Không rõ tên luật")
            doc_metadata["Số"] = law_metadata.get("number", "")
            doc_metadata["Ngày ban hành"] = law_metadata.get("promulgation_date", "")
            doc_metadata["Ngày hiệu lực"] = law_metadata.get("effective_date", "")
            doc_metadata["Tình trạng hiệu lực"] = law_metadata.get("expiration_date", "")
            doc_metadata["Ngày cập nhật"] = law_metadata.get("update_date", "")
            
            # lưu parent doc (sẽ được đưa vào redis)
            redis_payloads[parent_id] = {
                "text": parent_text,
                "metadata": doc_metadata
            }
            
            # Bước 2: tạo child chunks
            child_docs = self.child_splitter.split_text(parent_text)
            
            for child_text in child_docs:
                child_id = str(uuid4())
                
                # payload chuẩn bị cho quá trình tạo vector embedding
                qdrant_payloads.append({
                    "id": child_id,
                    "parent_id": parent_id,
                    "text": child_text,
                    "metadata": doc_metadata
                })
        
        return qdrant_payloads, redis_payloads
    
    def save_output(self, qdrant_data, redis_data, output_dir = "output"):
        os.makedirs(output_dir, exist_ok = True)
        
        qdrant_path = os.path.join(output_dir, "qdrant_child_chunks.json")
        redis_path = os.path.join(output_dir, "redis_parent_chunks.json")
        
        with open(qdrant_path, "w", encoding = "utf-8") as f:
            json.dump(qdrant_data, f, ensure_ascii = False, indent = 4)
        
        with open(redis_path, "w", encoding = "utf-8") as f:
            json.dump(redis_data, f, ensure_ascii = False, indent = 4)
        
        print(f"Đã lưu {len(qdrant_data)} child chunks vào: {qdrant_path}")
        print(f"Đã lưu {len(redis_data)} parent chunks vào: {redis_path}")

# --- Thực thi ---
if __name__ == "__main__":
    input_file = "./bo_luat_lao_dong_vbpl_structured.md"
    
    if not os.path.exists(input_file):
        print(f"Không tìm thấy file {input_file}. Vui lòng kiểm tra lại.")
    else:
        service = ChunkingService(input_file)
        qdrant_chunks, redis_chunks = service.process()
        service.save_output(qdrant_chunks, redis_chunks)