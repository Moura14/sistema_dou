MESES = ("janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro")
_NUM_MES = {m: i for i, m in enumerate(MESES, 1)}
_MESES_RE = "|".join(MESES).replace("marco", "mar[cç]o").upper()
_DATA = (r"\d{1,2}\s*[º°o]?\s+(?:de\s+)?[A-Za-zçÇ]+\s+de\s+\d{4}"
         r"|\d{1,2}[º°]?/\d{1,2}/\d{4}")