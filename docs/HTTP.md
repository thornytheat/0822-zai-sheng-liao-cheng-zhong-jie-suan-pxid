# 阶段接口

`POST /api/stages/<stage>` 接收 `multipart/form-data`。字段 `sample=dirty`、`sample=clean` 或 `file=<CSV>` 三选一。阶段为 `intake`、`prepare`、`calculate`、`policy`、`balance`。预览不入库。

`POST /api/runs` 接收同样的输入，执行全批并返回运行报告。`GET /api/runs` 返回最近 50 批。`GET /api/runs/<id>` 查询一批和当前复核状态。

`PATCH /api/runs/<id>` 接收 `revision`、`status` 和 `note`。状态使用 `APPROVED` 或 `HELD`。冲突返回 409，客户端读取新版本后重试。

`GET /api/runs/<id>` 与 `PATCH` 的响应附带 `ledger`，逐联单给出 `original_g`、`latest_g`、`paid_g`、`pending_g`、`recovery_g` 和状态。

## 更正补差

只有 `APPROVED` 批次可以更正，否则返回 409 `RUN_NOT_APPROVED`。`POST /api/runs/<id>/corrections` 接收 `file=<CSV>` 与可选 `reference`（最多 200 字），字段同阶段接口。

- 更正来源必须覆盖原签发已算出的全部联单，缺组或多组返回 409 `CORRECTION_SCOPE`。
- 每一张联单的付/欠都按 `最新应付 - 原签发应付 - 已补合计` 结算，单次更正可同时补多张联单。
- 每一次更正只补差额：`最新应付 - 原签发应付 - 已补合计`。已付不追回，累计补差正好等于最新应付与原签发应付之差。
- 同一份来源重复提交返回同一份更正，不重复生成补差；来源变化才算新的一次更正。
- 更正后杂质率超限或整批对账不符时，补差记为 `PENDING`，原签发金额不变；需要追回时同样停在待处理。
- 新的更正会把同联单尚未处理的补差标记为 `SUPERSEDED`，以最新来源为准。

`GET /api/runs/<id>/corrections` 列出更正记录，`GET /api/runs/<id>/corrections/<correction_id>` 查看单次更正的原金额、依据与逐联单补差。`GET /api/runs/<id>/ledger` 返回工作台台账：原签发、最新应付、已补、待处理、需追回与是否结清。

`GET /api/runs/<id>/evidence` 下载内含运行清单、行号隔离、业务证据、复核信息和补差台账的 JSON。
