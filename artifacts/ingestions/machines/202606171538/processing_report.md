# Processing & loading — machines

## Transformation (text → value)
- `maintenance_type` → `maintenance_type_code`
- `component` → `component_code`

## Imputation
- _(none)_

## Outliers (IQR clip)
- `duration_hours`: 13 clipped to [-0.205, 5.275]

## Database load

- 115 rows loaded into table 'maintenance'
