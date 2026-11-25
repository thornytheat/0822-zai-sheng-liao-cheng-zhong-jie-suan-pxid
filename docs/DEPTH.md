# 再生料称重结算规则登记

- 规模：中型

## 功能模块

| 模块 | 动作 | 接口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 样例采信 | 预览并定位坏行 | `POST /api/stages/intake` | `app/intake/service.py` | `tests/test_intake.py` |
| M2 过磅联单 | 检查领域约束 | `POST /api/stages/prepare` | `app/modules/prepare.py` | `tests/test_prepare.py` |
| M3 净干重核算 | 查看业务计算结果 | `POST /api/stages/calculate` | `app/modules/calculate.py` | `tests/test_calculate.py` |
| M4 结算复核 | 查看签收判定 | `POST /api/stages/policy` | `app/modules/policy.py` | `tests/test_policy.py` |
| M5 运行对账 | 对照输入、采信和隔离行 | `POST /api/stages/balance` | `app/modules/reconcile.py` | `tests/test_reconcile.py` |
| M6 批次复核 | 执行批次并签发或暂缓 | `POST /api/runs、PATCH /api/runs/<id>` | `app/review/service.py` | `tests/test_review.py` |
| M7 证据交付 | 下载复核清单 | `GET /api/runs/<id>/evidence` | `app/evidence/render.py` | `tests/test_evidence.py` |
| M8 更正补差 | 对已签发批次补差额 | `POST /api/runs/<id>/corrections` | `app/review/corrections.py`、`app/review/ledger.py` | `tests/test_corrections.py` |

## 输入陷阱

| 编号 | 规则 | 处理 | 测试 |
|---|---|---|---|
| TRAP-02 | 去除 BOM | `app/intake/reader.py` | `tests/test_intake.py::test_bom_preserves_identifier` |
| TRAP-03 | 按逻辑记录读取引号内换行 | `app/intake/reader.py` | `tests/test_intake.py::test_quoted_newline_is_one_logical_record` |
| TRAP-04 | 重复表头计入忽略行 | `app/intake/service.py` | `tests/test_intake.py::test_repeated_header_is_counted` |
| TRAP-05 | 异常列数隔离 | `app/intake/schema.py` | `tests/test_intake.py::test_extra_column_is_isolated` |
| TRAP-06 | 归一化全角数字和千分位 | `app/intake/numeric.py` | `tests/test_intake.py::test_full_width_and_grouping_are_canonical` |
| TRAP-07 | 空值行隔离 | `app/intake/numeric.py` | `tests/test_intake.py::test_sentinel_keeps_row_out_of_total` |
| TRAP-08 | 记录键保留前导零 | `app/intake/schema.py` | `tests/test_intake.py::test_bom_preserves_identifier` |
| TRAP-14 | 冲突版本都进入隔离 | `app/intake/resolve.py` | `tests/test_intake.py::test_duplicate_conflict_removes_both_copies` |
| TRAP-16 | 引号未闭合时拒收文件 | `app/intake/reader.py` | `tests/test_intake.py::test_unclosed_quote_invalidates_source` |
| TRAP-18 | 区分空文件、全空白和仅表头 | `app/intake/reader.py` | `tests/test_intake.py::test_empty_states_have_distinct_causes` |
| TRAP-26 | 拒绝旧版本复核 | `app/review/store.py` | `tests/test_review.py::test_review_optimistic_lock` |

## 领域反例

票号必须唯一，同车毛重在前、皮重在后，过磅间距最多 120 分钟。含水率按净重扣减，杂质率按干重扣减，每张联单最后向下取整。杂质率超过 2000 基点进入复核。

`sample_data/incoming.csv` 的 0003 组触发预检异常，0004 组触发业务判定。`tests/test_calculate.py` 还核对逐组结论和证据字段。

## 更正补差规则

| 编号 | 规则 | 处理 | 测试 |
|---|---|---|---|
| COR-01 | 只有已签发批次可以更正 | `app/review/corrections.py` | `tests/test_corrections.py::test_correction_requires_issued_batch` |
| COR-02 | 原金额与依据按签发报告原样读回 | `app/review/ledger.py` | `tests/test_corrections.py::test_correction_reads_back_original_amounts` |
| COR-03 | 每次只补差额，已付不追回 | `app/review/ledger.py` | `tests/test_corrections.py::test_two_corrections_accumulate_to_latest_gap` |
| COR-04 | 同一份更正重试不重复补差 | `app/review/store.py` | `tests/test_corrections.py::test_retry_does_not_duplicate` |
| COR-05 | 杂质率超限停在待处理 | `app/review/corrections.py` | `tests/test_corrections.py::test_contamination_after_correction_holds_supplement` |
| COR-06 | 整批对账不符停在待处理 | `app/review/corrections.py` | `tests/test_corrections.py::test_unbalanced_correction_pays_nothing` |
| COR-07 | 需追回时不动已付，记为待处理 | `app/review/ledger.py` | `tests/test_corrections.py::test_recovery_is_left_pending` |
| COR-08 | 工作台逐联单展示已补与待处理 | `app/review/store.py` | `tests/test_http.py::test_correction_ledger_on_workbench` |
