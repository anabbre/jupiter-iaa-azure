






def read_text_file(file_path):
    """Lee archivos de texto"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except:
        try:
            with open(file_path, 'r', encoding='latin-1') as f:
                return f.read()
        except Exception as e:
            return f"❌ Error leyendo archivo: {e}"
