import csv
import io

from app.intake.schema import HEADER

from conftest import csv_data


def rows_of(data):
    return list(csv.reader(io.StringIO(data.decode('utf-8-sig'), newline='')))[1:]


def rewrite(data, changes):
    """按 (分组, 类型, 票号) 改写 basis_points，返回新的 CSV 字节。"""
    output = []
    for row in rows_of(data):
        row = list(row)
        target = (row[1], row[2], row[3])
        if target in changes:
            row[7] = str(changes[target])
        output.append(row)
    return csv_data(output)


def only_groups(data, keep):
    return csv_data([row for row in rows_of(data) if row[1] in keep])
