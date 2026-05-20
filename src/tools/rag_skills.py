import os

def query_master_philosophy(params: dict) -> dict:
    try:
        topic = params.get("topic", "").lower()
        kb_dir = "data/expert_kb"
        
        if not os.path.exists(kb_dir):
            return {"status": "error", "message": "Knowledge base directory not found."}
            
        files = [f for f in os.listdir(kb_dir) if f.endswith(".md")]
        if not files:
            return {"status": "success", "data": {"content": "知识库中暂无大师备忘录。"}}
            
        content = ""
        matched = False
        
        if topic:
            for f in files:
                if topic in f.lower():
                    with open(os.path.join(kb_dir, f), "r", encoding="utf-8") as file:
                        content += f"--- {f} ---\n{file.read()}\n\n"
                    matched = True
                    
        if not matched:
            for f in files:
                with open(os.path.join(kb_dir, f), "r", encoding="utf-8") as file:
                    content += f"--- {f} ---\n{file.read()}\n\n"
                    
        return {"status": "success", "data": {"content": content.strip()}}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}
