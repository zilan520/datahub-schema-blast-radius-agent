# Schema Change Blast Radius

Dataset: `urn:li:dataset:(urn:li:dataPlatform:postgres,analytics.orders,PROD)`
Breaking findings: **2**

## Findings

- `informational` `added_field` `currency`
- `breaking` `type_changed` `customer_id` (STRING -> LONG)
- `breaking` `nullability_tightened` `customer_id`

## Downstream Impact

- `urn:li:dataJob:(urn:li:dataFlow:airflow,orders_daily,PROD)`
- `urn:li:dataset:(urn:li:dataPlatform:snowflake,warehouse.orders,PROD)`
- `urn:li:dashboard:(urn:li:dataPlatform:looker,orders,PROD)`

## Suggested Actions

- Review breaking findings with the owning team.
- Generate migration SQL or a PR only after a human reviews the proposed change.
- Write a governance tag or incident note back to DataHub after approval.
