"""Language-level operation/scope contracts, independent of dataset identities."""
import re
import unicodedata


def fold(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.casefold())
                   if unicodedata.category(c) != 'Mn').replace('đ', 'd')


def visible(text):
    # Quoted source values are data, not discourse instructions.
    return re.sub(r'"[^"\n]*"|“[^”\n]*”|`[^`\n]*`', '', fold(text))


def operations(text):
    text = visible(text)
    found = set()
    if re.search(r'\b(trung binh|average|mean)\b', text):
        found.add('avg')
    # Quantity questions such as 'xe này có bao nhiêu xi-lanh' ask for a
    # field value, not COUNT(*). Require explicit record-count language here.
    if re.search(r'\b(dem so|count|(?:bao nhieu|how many) (?:dong|ban ghi|records|rows))\b', text):
        found.add('count')
    return found


def scope_reference(text):
    return re.search(r'\b(?:nhom\b[^,;?.]{0,35}\b(?:nay|do)|cua chung|chung nay|'
                     r'nhung\b[^,;?.]{0,25}\b(?:nay|do)|same (?:group|records|rows)|'
                     r'these (?:records|rows)|those (?:records|rows)|of them)\b', visible(text))


def global_scope(text):
    return bool(re.search(r'\b(toan bang|toan bo bang|whole table|entire table|all records)\b', visible(text)))


def exception_reasoning(text):
    q=visible(text)
    return bool(re.search(r'\b(xet|kiem tra|tinh den|account(?:ing)? for|consider(?:ing)?|check)\b'
                          r'.{0,35}\b(moi ngoai le|tat ca cac ngoai le|all exceptions)\b',q)
                or re.search(r'\b(khong|without|no)\b.{0,45}\b(bat ky dieu kien|any conditions|any requirements|conditions whatsoever)\b',q)
                or re.search(r'\b(vo dieu kien|unconditionally)\b',q))


def zero_price(predicate, table, quote):
    """Only a numeric price field can encode an explicit free-of-charge request."""
    return (predicate['value'] in ('0', '0.0') and predicate['operator'] == 'eq'
            and table.types.get(predicate['column']) in ('BIGINT', 'DOUBLE')
            and re.search(r'\b(price|cost|fee|gia|phi)\b', fold(predicate['column']).replace('_', ' '))
            and re.search(r'\b(mien phi|free of charge|free)\b', visible(quote))
            and not re.search(r'\b(khong|not|khong phai|not necessarily)\s+(?:duoc\s+)?(?:mien phi|free)', visible(quote)))
