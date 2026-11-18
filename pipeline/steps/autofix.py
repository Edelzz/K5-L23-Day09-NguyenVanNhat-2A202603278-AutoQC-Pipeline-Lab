"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict

import yaml

from ..common import ERROR, parse_yolo_line


DROP_LINE = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
REMOVE_IMAGE = {"DUP_IMAGE_EXACT", "DUP_IMAGE_NEAR", "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}


def _change(image, line, action, before, after):
    return {"image": image, "line": line, "action": action, "before": before, "after": after}


def _clip_box(content):
    class_id, cx, cy, width, height = parse_yolo_line(content)
    left, top = cx - width / 2, cy - height / 2
    right, bottom = cx + width / 2, cy + height / 2
    if 0 <= left < right <= 1 and 0 <= top < bottom <= 1:
        return content
    left, top = max(0.0, left), max(0.0, top)
    right, bottom = min(1.0, right), min(1.0, bottom)
    if left >= right or top >= bottom:
        return None
    clipped = ((left + right) / 2, (top + bottom) / 2, right - left, bottom - top)
    return " ".join([str(class_id), *(str(value) for value in clipped)])


def _fix_lines(path, errors_by_line):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    updated = []
    fixes = []
    for number, content in enumerate(lines, 1):
        codes = errors_by_line.get(number, set())
        if codes & DROP_LINE:
            after = None
        elif "BOX_OUT_OF_IMAGE" in codes:
            after = _clip_box(content)
        else:
            after = content

        if after is None:
            fixes.append(_change(path.stem, number, "drop_line", content, ""))
        else:
            updated.append(after)
            if after != content:
                fixes.append(_change(path.stem, number, "clip_box", content, after))

    if fixes:
        path.write_text("".join(line + "\n" for line in updated), encoding="utf-8")
    return fixes


def _rename_classes(path, classes):
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, UnicodeError, yaml.YAMLError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    before = data.get("names")
    if before == classes:
        return None
    data["names"] = classes
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return _change(path.name, None, "rename_classes", before, classes)


def fix(ds, issues, cfg):
    errors_by_image = defaultdict(list)
    for issue in issues:
        if issue.severity == ERROR:
            errors_by_image[issue.image].append(issue)

    images = defaultdict(list)
    for path in ds.image_files():
        images[path.stem].append(path)

    fixes = []
    for stem, errors in sorted(errors_by_image.items()):
        codes = {issue.code for issue in errors}
        if "BAD_CLASS_NAME" in codes:
            change = _rename_classes(ds.yaml_path, cfg["classes"])
            if change is not None:
                fixes.append(change)

        label = ds.label_path(stem)
        if codes & REMOVE_IMAGE:
            removed_images = images.get(stem, [])
            for path in removed_images:
                path.unlink(missing_ok=True)
            if removed_images or label.exists():
                label.unlink(missing_ok=True)
                fixes.append(_change(stem, None, "remove_image",
                                     ", ".join(path.name for path in removed_images), ""))
            continue

        if not label.exists():
            if "MISSING_LABEL_FILE" in codes and stem in images:
                fixes.append(_change(stem, None, "needs_label", "(không có file)", "chuyển người gán"))
            continue

        errors_by_line = defaultdict(set)
        for issue in errors:
            if issue.line is not None and (issue.code in DROP_LINE or issue.code == "BOX_OUT_OF_IMAGE"):
                errors_by_line[issue.line].add(issue.code)
        if errors_by_line:
            fixes.extend(_fix_lines(label, errors_by_line))

    return fixes
