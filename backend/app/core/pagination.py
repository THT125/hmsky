"""统一分页:与原项目 PageResult {total, records} 对齐"""


def page_result(total: int, records: list) -> dict:
    return {"total": total, "records": records}
