# 再生料称重结算

回收站结算员可在工作台上传来源 CSV，对照规则判断差异，签发合格批次或记录暂缓意见。

配对同车进出磅，按整数克扣除实测含水和杂质，冻结无有效皮重的票据。

## 启动

```sh
docker compose up --build -d --wait
```

打开 <http://localhost:18321>。页面预览带异常样例。选中阶段查看计算证据，选择可签发样例并执行批次，然后提交复核意见。

## 核验

```sh
docker compose exec -T app pytest -q
```

[输入字段](docs/DATA-DICTIONARY.md) · [阶段接口](docs/HTTP.md) · [操作步骤](docs/OPERATIONS.md) · [规则与测试](docs/DEPTH.md)
